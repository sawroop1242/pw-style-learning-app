"""Only timing modes the platform actually enforces can be chosen.

Audit finding 4: `Quiz.TimingMode` advertised `section_timed` and
`total_and_section`, but there is no section entity with a duration, an order or
a navigation policy, so an attempt started in either mode simply ran untimed —
a page promising per-section clocks and a server that keeps none. The modes are
refused until sections exist; these tests pin the refusal.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import Course, Quiz, QuizAttempt

User = get_user_model()


class SectionTimingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="timing", email="t@example.com", password="TestPass123!", is_staff=True
        )
        cls.owner.profile.role = Role.SUB_ADMIN
        cls.owner.profile.save()
        cls.course = Course.objects.create(
            title="Batch", slug="timing-batch", owner=cls.owner, is_published=True
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def create(self, **overrides):
        payload = {"course": self.course.id, "title": "Paper", "timing_mode": "timed",
                   "duration_minutes": 60}
        payload.update(overrides)
        return self.client.post("/api/staff/quizzes/", payload, format="json")

    def test_section_timed_is_refused_on_create(self):
        response = self.create(timing_mode="section_timed")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("timing_mode", response.json())
        self.assertFalse(Quiz.objects.filter(title="Paper").exists())

    def test_total_and_section_is_refused_on_create(self):
        response = self.create(timing_mode="total_and_section", duration_minutes=90)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("timing_mode", response.json())

    def test_section_timed_is_refused_on_update(self):
        quiz = Quiz.objects.create(course=self.course, title="Whole clock", timing_mode="timed",
                                   duration_minutes=30)
        response = self.client.patch(
            f"/api/staff/quizzes/{quiz.id}/", {"timing_mode": "section_timed"}, format="json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        quiz.refresh_from_db()
        self.assertEqual(quiz.timing_mode, "timed")

    def test_timed_needs_a_duration(self):
        response = self.create(duration_minutes=None)
        self.assertEqual(response.status_code, 400, response.content)

    def test_timed_and_untimed_still_work(self):
        self.assertEqual(self.create(title="Clock", timing_mode="timed").status_code, 201)
        self.assertEqual(
            self.create(title="Practice", timing_mode="untimed", duration_minutes=None).status_code,
            201,
        )

    def test_the_model_refuses_it_too(self):
        """The admin form calls full_clean, so it must not be a serializer-only rule."""
        quiz = Quiz(course=self.course, title="Sneaky", timing_mode="section_timed",
                    duration_minutes=30)
        with self.assertRaises(ValidationError) as caught:
            quiz.full_clean()
        self.assertIn("timing_mode", caught.exception.message_dict)

    def test_an_attempt_on_an_unsupported_mode_has_no_clock_to_keep(self):
        """Why this matters: without the refusal, this paper runs untimed."""
        quiz = Quiz.objects.create(course=self.course, title="Legacy", timing_mode="section_timed",
                                   duration_minutes=10, is_published=True)
        response = self.client.post("/api/quizzes/start/", {"quiz_id": quiz.id}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        attempt = QuizAttempt.objects.get(pk=response.json()["id"])
        # No deadline was created, which is exactly the misleading case the
        # refusal prevents for new papers.
        self.assertIsNone(attempt.deadline)
        self.assertTrue(quiz.duration_minutes > 0)
        attempt.deadline = timezone.now() + timedelta(minutes=1)
        attempt.save(update_fields=["deadline"])
