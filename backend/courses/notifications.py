"""The notification inbox, computed from rows that already exist.

There is no ``Notification`` table. An announcement is a ``CommunityPost``, a
reminder is a ``StudyTask`` that has fallen due, and a "your result is out" is a
``QuizAttempt`` whose result was released. Copying those into a second table
would mean two places to keep true, and the copy is always the one that rots.

What cannot be derived is "I have already seen this", so only that is stored —
``NotificationRead``. Everything else here is a read-only projection.

Rules that keep the inbox honest:

* Only what the caller may already read appears. Course-scoped announcements
  need access to that course; tasks and attempts are the caller's own.
* Nothing is invented. No "come back tomorrow", no marketing, no streak guilt —
  the planner spec forbids marketing notifications by default.
* A guest has no identity, so a guest inbox holds public announcements only.
"""

from datetime import timedelta

from django.utils import timezone

from .models import CommunityPost, NotificationRead, QuizAttempt, StudyTask
from .policy import can_access_course

ANNOUNCEMENT_WINDOW_DAYS = 14
RESULT_WINDOW_DAYS = 7
MAX_ITEMS = 20


def _announcements(user):
    """Published notices the caller can see, newest first."""
    posts = (
        CommunityPost.objects.filter(is_published=True)
        .select_related("course")
        .order_by("-is_pinned", "-created_at")[:MAX_ITEMS]
    )
    horizon = timezone.now() - timedelta(days=ANNOUNCEMENT_WINDOW_DAYS)
    items = []
    for post in posts:
        if post.course_id is not None and not can_access_course(user, post.course):
            continue
        if post.created_at < horizon and not post.is_pinned:
            continue
        items.append(
            {
                "id": f"announcement:{post.id}",
                "kind": "announcement",
                "title": post.title,
                "body": post.body[:160],
                "href": "community.html",
                "at": post.created_at.isoformat(),
            }
        )
    return items


def _due_tasks(user):
    """Tasks that need attention today: overdue or due by the end of today."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    end_of_today = timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0)
    tasks = (
        StudyTask.objects.filter(user=user, is_completed=False, due_at__isnull=False)
        .filter(due_at__lte=end_of_today)
        .order_by("due_at")[:MAX_ITEMS]
    )
    items = []
    for task in tasks:
        overdue = task.due_at < timezone.now()
        items.append(
            {
                "id": f"task:{task.id}",
                "kind": "task",
                "title": task.title,
                "body": (
                    "Overdue — this task was due "
                    if overdue
                    else "Due today"
                )
                + task.due_at.strftime("%d %b, %H:%M"),
                "href": "dashboard.html#task-list",
                "at": task.due_at.isoformat(),
            }
        )
    return items


def _released_results(user):
    """Attempts whose result came out recently — the learner has not looked yet."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    horizon = timezone.now() - timedelta(days=RESULT_WINDOW_DAYS)
    attempts = (
        QuizAttempt.objects.filter(
            user=user, result_released_at__gte=horizon, result_released_at__isnull=False
        )
        .select_related("quiz")
        .order_by("-result_released_at")[:MAX_ITEMS]
    )
    items = []
    for attempt in attempts:
        percent = None
        if attempt.score is not None and attempt.max_score:
            percent = round(float(attempt.score) / float(attempt.max_score) * 100)
        items.append(
            {
                "id": f"result:{attempt.id}",
                "kind": "result",
                "title": attempt.quiz.title,
                "body": "Result released"
                + (f" — {percent}%" if percent is not None else ""),
                "href": f"test-player.html?test={attempt.quiz_id}&attempt={attempt.id}",
                "at": attempt.result_released_at.isoformat(),
            }
        )
    return items


def build_inbox(user):
    """Every item this caller may see, newest first, with a read flag."""
    items = _announcements(user) + _due_tasks(user) + _released_results(user)
    items.sort(key=lambda item: item["at"], reverse=True)
    items = items[:MAX_ITEMS]

    read = set()
    if user is not None and getattr(user, "is_authenticated", False):
        read = set(
            NotificationRead.objects.filter(
                user=user, key__in=[item["id"] for item in items]
            ).values_list("key", flat=True)
        )
    for item in items:
        item["read"] = item["id"] in read

    return {
        "count": len(items),
        "unread": sum(1 for item in items if not item["read"]),
        "results": items,
    }


def mark_read(user, keys):
    """Record that ``keys`` have been seen. Returns how many became read."""
    if user is None or not getattr(user, "is_authenticated", False):
        return 0
    known = {item["id"] for item in build_inbox(user)["results"]}
    wanted = [key for key in keys if key in known]
    already = set(
        NotificationRead.objects.filter(user=user, key__in=wanted).values_list("key", flat=True)
    )
    fresh = [NotificationRead(user=user, key=key) for key in wanted if key not in already]
    if fresh:
        NotificationRead.objects.bulk_create(fresh, ignore_conflicts=True)
    return len(fresh)
