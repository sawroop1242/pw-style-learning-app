"""The timetable: what is on, when, and whether it is on *now*.

Why this module exists
----------------------
The home page's "Today's classes" used to mean *classes uploaded today* — a
recording pushed at 11pm for tomorrow's class counted as today's, and the class
scheduled for this evening did not appear at all. A timetable has to be built
from a time, not from a row's creation date.

The rules it enforces
---------------------
* **One clock.** Every status comes from the same ``now`` passed into the
  build, so two classes can never disagree about what "now" is.
* **Nothing claims to be live.** Every class here is a recording published at
  an embed URL; none of them is a stream. So the timetable says when a class
  airs and whether that hour has passed — ``upcoming`` or ``ended`` — and never
  "live now". There is no ``is_live`` column to go stale either.
* **On-demand lessons are not scheduled.** A lesson without ``starts_at`` is
  not on the timetable; it never appears, rather than appearing at "00:00".
* **The day is a record.** Today's group keeps the classes that already
  passed this morning — a timetable you can only read forwards is not a
  timetable.
* **A blank duration is not invented.** Duration 0 means the class has no
  stated length; the hour it airs still stands. The admin says so; this module
  does not guess "maybe an hour".
"""

from datetime import timedelta

from django.utils import timezone

from . import policy
from .models import Course, Lesson

#: Days of timetable a request may ask for, and the default.
DEFAULT_DAYS = 7
MIN_DAYS = 1
MAX_DAYS = 30

STATUS_UPCOMING = "upcoming"
STATUS_ENDED = "ended"


def clamp_days(raw):
    """Turn ``?days=`` into a number of days, clamped, never an error.

    A window is a view preference, not a resource: ``days=abc`` showing a week
    is friendlier than a 400, and the payload reports the window it used.
    """
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_DAYS
    return max(MIN_DAYS, min(MAX_DAYS, days))


def ends_at(lesson):
    """When the class is over — start plus its own duration."""
    return lesson.starts_at + timedelta(minutes=lesson.duration_minutes or 0)


def status_for(lesson, now):
    """``upcoming`` before the class airs, ``ended`` once it has.

    The boundary is the start, not the end: a recording is published at its
    class time, so from that minute the class is there to watch. Nothing here
    ever says "live" — these are embeds, and a badge that claims a stream is a
    lie the product would have to keep telling.
    """
    return STATUS_UPCOMING if now < lesson.starts_at else STATUS_ENDED


def _day_label(day):
    """``Thursday, 5 November`` — no zero padding, no locale surprises."""
    return f"{day.strftime('%A')}, {day.day} {day.strftime('%B')}"


def _entry(lesson, now, can_open):
    """One class as the timetable shows it. Never carries the video URL."""
    course = lesson.course
    recording = bool((lesson.video_url or "").strip())
    return {
        "id": lesson.id,
        "title": lesson.title,
        "section": lesson.folder.title if lesson.folder_id else "",
        "starts_at": timezone.localtime(lesson.starts_at).isoformat(),
        "ends_at": timezone.localtime(ends_at(lesson)).isoformat(),
        "duration_minutes": lesson.duration_minutes or 0,
        "status": status_for(lesson, now),
        "recording": recording,
        # A recording the caller may not open is still a fact ("there is one"),
        # so it is reported as locked rather than hidden.
        "is_locked": recording and not can_open,
        "can_open": can_open,
        "course": {
            "id": course.id,
            "title": course.title,
            "slug": course.slug,
        },
    }


def _visible_course_ids(user, granted=None):
    """Batches whose timetable this account may see as *its own*.

    The same rule as the lesson list: an active grant, plus batches the caller
    owns so staff can preview their own work. Enrolment is explicit, so a free
    batch the learner never joined is not in their timetable.

    ``granted`` may be passed pre-fetched; the build reads the table once and
    uses the same set for the visible batches and the per-class lock state.
    """
    if granted is None:
        granted = policy.granted_course_ids(user)
    owned = set(
        Course.objects.filter(owner=user).values_list("id", flat=True)
    ) if getattr(user, "is_authenticated", False) else set()
    return granted | owned


def build(*, user, days=DEFAULT_DAYS, course=None, now=None):
    """The timetable payload for one learner, or for one batch.

    ``course`` switches the build from "my week" to "this batch's week". A
    batch's timetable is public metadata — the batch page already prints every
    lesson title — so it does not require an account. Recordings still do:
    ``can_open`` is computed for the caller either way.
    """
    now = now or timezone.now()
    days = clamp_days(days)
    local_today = timezone.localtime(now).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    window_end = local_today + timedelta(days=days)

    granted = policy.granted_course_ids(user)

    if course is not None:
        courses = Course.objects.filter(pk=course.pk)
        scope = "course"
    else:
        courses = Course.objects.filter(
            pk__in=_visible_course_ids(user, granted), is_published=True
        )
        scope = "mine"

    lessons = (
        Lesson.objects.filter(
            is_published=True,
            starts_at__isnull=False,
            starts_at__gte=local_today,
            starts_at__lt=window_end,
            course__is_published=True,
            course__in=courses,
        )
        # ``owner`` rides along because the access rule asks who owns the
        # batch; without it that is one query per batch, the fan-out this
        # timetable must not have.
        .select_related("course", "course__owner", "folder")
        .order_by("starts_at", "id")
    )

    # One access decision per batch, not one per class: a week of a busy batch
    # is a dozen lessons and the same course row every time.
    access = {}

    def can_open(lesson):
        if lesson.course_id not in access:
            access[lesson.course_id] = policy.can_consume_course(
                user, lesson.course, granted=granted
            )
        return access[lesson.course_id]

    groups = []
    by_day = {}
    upcoming = today_count = total = 0
    next_class = None

    for lesson in lessons:
        entry = _entry(lesson, now, can_open(lesson))
        total += 1
        if entry["status"] == STATUS_UPCOMING:
            upcoming += 1
        if next_class is None and entry["status"] == STATUS_UPCOMING:
            next_class = entry

        day = timezone.localtime(lesson.starts_at).date()
        if day not in by_day:
            group = {
                "date": day.isoformat(),
                "label": _day_label(day),
                "is_today": day == local_today.date(),
                "classes": [],
            }
            by_day[day] = group
            groups.append(group)
        by_day[day]["classes"].append(entry)
        if day == local_today.date():
            today_count += 1

    payload = {
        "timezone": timezone.get_current_timezone_name(),
        "now": timezone.localtime(now).isoformat(),
        "scope": scope,
        "window_days": days,
        "counts": {
            "today": today_count,
            "upcoming": upcoming,
            "total": total,
        },
        "groups": groups,
        "next": next_class,
    }
    if course is not None:
        payload["course"] = {"id": course.id, "title": course.title, "slug": course.slug}
    return payload
