"""The timetable — P5.

Two things can go wrong with a schedule, and both have shipped elsewhere:

* **A claim the product cannot keep.** These classes are recordings at an
  embed URL, never a stream, so nothing here may say "live". A stored flag
  keeps saying it after the class ended; a computed window still claims a
  broadcast that does not exist. The timetable therefore has two states —
  ``upcoming`` before the hour, ``ended`` after it — computed from one ``now``
  per build, so every class in a payload agrees about what time it is.
* **A class that appears at a made-up hour.** A lesson with no ``starts_at`` is
  not on the timetable. It is left out rather than parked at midnight.

The tests also pin the parts that are easy to get subtly wrong: today's finished
classes stay in today's group, the window is local midnight to local midnight,
and a recording the caller may not open is reported as locked rather than
hidden or leaked.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from courses import schedule
from courses.models import Course, CourseAccessGrant, CourseFolder, Lesson

User = get_user_model()


def at(now, **delta):
    """``now`` shifted by keyword deltas, e.g. ``at(now, minutes=-12)``."""
    return now + timedelta(**delta)


class ClampTests(SimpleTestCase):
    def test_a_window_is_clamped_not_rejected(self):
        self.assertEqual(schedule.clamp_days(None), schedule.DEFAULT_DAYS)
        self.assertEqual(schedule.clamp_days("abc"), schedule.DEFAULT_DAYS)
        self.assertEqual(schedule.clamp_days("0"), schedule.MIN_DAYS)
        self.assertEqual(schedule.clamp_days("999"), schedule.MAX_DAYS)
        self.assertEqual(schedule.clamp_days("3"), 3)


class DurationTests(SimpleTestCase):
    def test_a_blank_duration_is_not_turned_into_an_hour(self):
        starts = timezone.now().replace(microsecond=0)
        lesson = Lesson(starts_at=starts, duration_minutes=0)

        self.assertEqual(schedule.ends_at(lesson), starts)
        self.assertEqual(schedule.status_for(lesson, starts - timedelta(minutes=1)), "upcoming")
        self.assertEqual(schedule.status_for(lesson, starts), "ended")


class ScheduleData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="provider", email="p@example.com", password="TestPass123!", is_staff=True
        )
        cls.owner.profile.role = Role.SUB_ADMIN
        cls.owner.profile.save()
        cls.learner = User.objects.create_user(
            username="learner", email="l@example.com", password="TestPass123!"
        )
        cls.other = User.objects.create_user(
            username="other", email="o@example.com", password="TestPass123!"
        )

        def batch(slug, title, published=True, free=True):
            return Course.objects.create(
                title=title,
                slug=slug,
                owner=cls.owner,
                is_published=published,
                pricing_mode=Course.PricingMode.FREE if free else Course.PricingMode.PAID,
                price=Decimal("0.00") if free else Decimal("4999.00"),
            )

        cls.course = batch("jee-2027", "JEE 2027")
        cls.folder = CourseFolder.objects.create(course=cls.course, title="Mechanics")
        cls.other_course = batch("neet-2027", "NEET 2027")
        cls.other_folder = CourseFolder.objects.create(course=cls.other_course, title="Cell")
        cls.hidden_course = batch("draft", "Draft batch", published=False)

    def setUp(self):
        # A controlled clock: every case below states its offsets from this.
        self.now = timezone.now().replace(microsecond=0)
        self.today = timezone.localtime(self.now).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.client = APIClient()

    def lesson(self, title, starts_at, course=None, folder="default", published=True, **extra):
        course = course or self.course
        if folder == "default":
            folder = self.folder if course is self.course else self.other_folder
        return Lesson.objects.create(
            course=course,
            folder=folder,
            title=title,
            starts_at=starts_at,
            is_published=published,
            **extra,
        )

    def enrol(self, user=None, course=None):
        return CourseAccessGrant.objects.create(
            user=user or self.learner, course=course or self.course
        )

    def payload(self, **kwargs):
        kwargs.setdefault("user", self.learner)
        kwargs.setdefault("now", self.now)
        return schedule.build(**kwargs)

    def titles(self, payload):
        return [entry["title"] for group in payload["groups"] for entry in group["classes"]]


class StatusAndGroupingTests(ScheduleData):
    def test_the_two_states_are_computed_from_one_clock(self):
        # Anchored to *now*, never to a wall-clock hour: a fixture at "19:00
        # today" is already over when the suite runs at 20:00, and the test
        # then fails for the time of day rather than for the code.
        ended = self.lesson("Ended", at(self.now, hours=-3))
        now = self.lesson("Now", at(self.now, minutes=-12), duration_minutes=52)
        later = self.lesson("Later", at(self.now, minutes=90))
        self.enrol()

        entries = {
            entry["title"]: entry["status"]
            for group in self.payload()["groups"]
            for entry in group["classes"]
        }
        self.assertEqual(entries["Ended"], "ended")
        self.assertEqual(entries["Now"], "ended")
        self.assertEqual(entries["Later"], "upcoming")
        self.assertIs(ended.starts_at < self.now, True)

    def test_a_class_that_started_is_not_called_live(self):
        """The video is an embed. The moment it airs, it is simply there."""
        lesson = self.lesson("Published", at(self.now, minutes=-1), duration_minutes=52)

        for moment in (self.now, at(self.now, minutes=10)):
            self.assertEqual(schedule.status_for(lesson, moment), "ended")
        self.assertEqual(schedule.status_for(lesson, at(self.now, minutes=-2)), "upcoming")

    def test_no_payload_carries_a_live_count(self):
        self.lesson("Mine", at(self.now, minutes=-12))
        self.enrol()

        counts = self.payload()["counts"]
        self.assertNotIn("live", counts)
        self.assertEqual(set(counts), {"today", "upcoming", "total"})

    def test_todays_finished_class_stays_on_todays_list(self):
        # Fixed to today rather than to now: the assertions are about *which
        # day* the class is grouped under, and they hold whether the class is
        # behind the clock or ahead of it. Only the status assertions above
        # need a clock-relative fixture.
        self.lesson("This morning", at(self.today, hours=9))
        self.enrol()

        payload = self.payload()
        group = payload["groups"][0]
        self.assertTrue(group["is_today"])
        self.assertEqual([entry["title"] for entry in group["classes"]], ["This morning"])
        self.assertEqual(payload["counts"]["today"], 1)

    def test_a_class_without_an_air_time_is_not_scheduled(self):
        self.lesson("Recording only", None)
        self.lesson("Real class", at(self.today, hours=19))
        self.enrol()

        self.assertEqual(self.titles(self.payload()), ["Real class"])

    def test_unpublished_classes_and_batches_are_left_out(self):
        self.lesson("Draft class", at(self.today, hours=19), published=False)
        self.lesson(
            "Draft batch class",
            at(self.today, hours=19),
            course=self.hidden_course,
            folder=None,
        )
        self.lesson("Real class", at(self.today, hours=19))
        self.enrol()

        self.assertEqual(self.titles(self.payload()), ["Real class"])

    def test_the_window_is_local_days_and_excludes_the_day_after_it(self):
        self.lesson("Day 1", at(self.today, hours=19))
        self.lesson("Day 7", at(self.today, days=6, hours=19))
        self.lesson("Day 8", at(self.today, days=7, hours=19))
        self.enrol()

        payload = self.payload(days=7)
        self.assertEqual(self.titles(payload), ["Day 1", "Day 7"])
        self.assertEqual([group["date"] for group in payload["groups"]], [
            (self.today + timedelta(days=0)).date().isoformat(),
            (self.today + timedelta(days=6)).date().isoformat(),
        ])

    def test_classes_are_ordered_by_time_within_a_day(self):
        self.lesson("Evening", at(self.today, hours=21))
        self.lesson("Morning", at(self.today, hours=8))
        self.enrol()

        day = self.payload()["groups"][0]
        self.assertEqual([entry["title"] for entry in day["classes"]], ["Morning", "Evening"])

    def test_next_is_the_first_class_that_has_not_ended(self):
        self.lesson("Finished", at(self.now, hours=-4))
        self.lesson("Next up", at(self.now, minutes=120))
        self.lesson("After that", at(self.now, days=1))
        self.enrol()

        self.assertEqual(self.payload()["next"]["title"], "Next up")

    def test_next_is_null_when_everything_has_finished(self):
        self.lesson("Finished", at(self.now, hours=-4))
        self.enrol()

        self.assertIsNone(self.payload()["next"])
        self.assertEqual(self.payload()["counts"]["upcoming"], 0)


class ScopeTests(ScheduleData):
    def test_a_batch_never_joined_is_not_in_this_learners_week(self):
        self.lesson("Mine", at(self.today, hours=19))
        self.lesson(
            "Theirs", at(self.today, hours=19), course=self.other_course
        )
        self.enrol()

        self.assertEqual(self.titles(self.payload()), ["Mine"])

    def test_enrolling_in_the_second_batch_brings_its_classes_in(self):
        self.lesson("Mine", at(self.today, hours=19))
        self.lesson("Theirs", at(self.today, hours=20), course=self.other_course)
        self.enrol()

        self.assertEqual(self.titles(self.payload()), ["Mine"])

        self.enrol(course=self.other_course)
        self.assertEqual(self.titles(self.payload()), ["Mine", "Theirs"])

    def test_an_owner_previews_their_own_batch_without_enrolling(self):
        self.lesson("Owner's class", at(self.today, hours=19))

        self.assertEqual(self.titles(self.payload(user=self.owner)), ["Owner's class"])

    def test_one_batchs_timetable_is_public(self):
        self.lesson("Mine", at(self.today, hours=19))
        self.lesson("Theirs", at(self.today, hours=20), course=self.other_course)

        payload = self.payload(user=None, course=self.other_course)
        self.assertEqual(payload["scope"], "course")
        self.assertEqual(self.titles(payload), ["Theirs"])
        self.assertEqual(payload["course"]["slug"], "neet-2027")


class AccessTests(ScheduleData):
    def test_a_recording_the_caller_cannot_open_is_locked_not_hidden(self):
        paid = Course.objects.create(
            title="Paid batch",
            slug="paid-batch",
            owner=self.owner,
            is_published=True,
            pricing_mode=Course.PricingMode.PAID,
            price=Decimal("4999.00"),
        )
        folder = CourseFolder.objects.create(course=paid, title="Week 1")
        self.lesson(
            "Paid class",
            at(self.today, hours=19),
            course=paid,
            folder=folder,
            video_url="https://cdn.example/paid.mp4",
        )

        entry = self.payload(user=None, course=paid)["groups"][0]["classes"][0]
        self.assertTrue(entry["recording"])
        self.assertTrue(entry["is_locked"])
        self.assertFalse(entry["can_open"])

    def test_the_payload_never_carries_the_video_url(self):
        self.lesson(
            "Mine",
            at(self.today, hours=19),
            video_url="https://cdn.example/secret.mp4",
        )
        self.enrol()

        payload = self.payload()
        self.assertNotIn("secret.mp4", str(payload))
        self.assertTrue(payload["groups"][0]["classes"][0]["recording"])
        self.assertTrue(payload["groups"][0]["classes"][0]["can_open"])


class ScheduleApiTests(ScheduleData):
    def api(self, query="", user=None):
        if user is not None:
            self.client.force_authenticate(user)
        return self.client.get(f"/api/schedule/{query}")

    def test_a_guest_is_asked_to_sign_in_for_their_own_timetable(self):
        response = self.api()
        self.assertEqual(response.status_code, 401)
        self.assertIn("Sign in", response.json()["detail"])

    def test_a_signed_in_learner_gets_the_week(self):
        self.lesson("Mine", at(self.now, minutes=60))
        self.enrol()
        response = self.api(user=self.learner)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["scope"], "mine")
        self.assertEqual(body["window_days"], schedule.DEFAULT_DAYS)
        self.assertEqual(body["counts"]["total"], 1)
        self.assertEqual(body["groups"][0]["classes"][0]["title"], "Mine")
        self.assertIn("now", body)

    def test_a_batchs_timetable_is_reachable_by_slug_and_by_id(self):
        self.lesson("Mine", at(self.now, minutes=60))

        by_slug = self.api("?course=jee-2027")
        by_id = self.api(f"?course={self.course.id}")

        self.assertEqual(by_slug.status_code, 200)
        self.assertEqual(by_slug.json()["groups"], by_id.json()["groups"])
        self.assertEqual(by_slug.json()["counts"]["total"], 1)

    def test_an_unpublished_or_unknown_batch_is_a_404(self):
        self.assertEqual(self.api("?course=draft").status_code, 404)
        self.assertEqual(self.api("?course=no-such-batch").status_code, 404)
        self.assertEqual(self.api("?course=999999").status_code, 404)

    def test_the_window_is_reported_as_applied(self):
        self.assertEqual(self.api("?course=jee-2027&days=2").json()["window_days"], 2)
        self.assertEqual(self.api("?course=jee-2027&days=999").json()["window_days"], 30)
        self.assertEqual(self.api("?course=jee-2027&days=abc").json()["window_days"], 7)

    def test_a_course_timetable_does_not_require_an_account(self):
        self.lesson("Mine", at(self.now, minutes=60))
        response = self.api("?course=jee-2027")
        self.assertEqual(response.status_code, 200)

    def test_the_route_is_listed_in_the_api_root(self):
        names = self.client.get("/api/").json()
        self.assertEqual(names["schedule"], "/api/schedule/")

    def test_the_batch_page_is_told_which_clock_the_times_are_on(self):
        """The day headings are cut on this zone, so the clocks must match it."""
        timetable = self.api("?course=jee-2027").json()
        detail = self.client.get(f"/api/courses/{self.course.id}/").json()

        self.assertEqual(timetable["timezone"], detail["timezone"])
        self.assertEqual(detail["timezone"], timezone.get_current_timezone_name())

    def test_a_week_of_many_batches_does_not_cost_a_query_per_batch(self):
        """The grant table is read once, not once per class.

        A timetable joins a learner's batches; the lock state of each class
        needs the same answer the batch list already computed. Asking the
        database again per row is the classic fan-out, and the count below is
        the proof it does not happen.
        """
        self.enrol()
        for index in range(4):
            course = Course.objects.create(
                title=f"Batch {index}",
                slug=f"batch-{index}",
                owner=self.owner,
                pricing_mode=Course.PricingMode.FREE,
                is_published=True,
            )
            folder = CourseFolder.objects.create(course=course, title="Week")
            CourseAccessGrant.objects.create(user=self.learner, course=course)
            self.lesson(f"Class {index}", at(self.now, minutes=60), course=course, folder=folder)

        with self.assertNumQueries(3):
            # grants once, the learner's batches once, the lessons once — the
            # owner rides along on the lesson join. Five batches or one, this
            # is the cost.
            response = self.api(user=self.learner)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"]["total"], 4)

    def test_the_timezone_is_not_shipped_to_a_catalogue_grid(self):
        """A card with no air time has nothing to print it for."""
        row = self.client.get("/api/courses/").json()["results"][0]
        self.assertNotIn("timezone", row)
