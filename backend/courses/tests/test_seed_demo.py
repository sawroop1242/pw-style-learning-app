"""Tests for the ``seed_demo`` management command.

The command exists so the front end can be exercised against a real API, which
only works if three things hold: it is safe to re-run, it deletes only its own
rows, and what it creates is actually reachable by an anonymous visitor.
"""

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from courses.models import (
    Choice,
    Course,
    CourseFolder,
    Lesson,
    PdfResource,
    Question,
    Quiz,
    TestSeries,
)


def run(*args):
    out = StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


class SeedDemoTests(TestCase):
    def test_creates_a_published_catalogue(self):
        run()

        courses = Course.objects.filter(slug__startswith="demo-")
        self.assertGreaterEqual(courses.count(), 5)
        self.assertTrue(all(course.is_published for course in courses))
        self.assertTrue(CourseFolder.objects.exists())
        self.assertTrue(Lesson.objects.filter(is_published=True).exists())

        paid = courses.filter(pricing_mode=Course.PricingMode.PAID).first()
        free = courses.filter(pricing_mode=Course.PricingMode.FREE).first()
        self.assertGreater(paid.price, Decimal("0"))
        self.assertEqual(free.price, Decimal("0"))

    def test_creates_sit_able_published_tests(self):
        run()

        quizzes = Quiz.objects.all()
        self.assertGreaterEqual(quizzes.count(), 4)
        self.assertTrue(all(quiz.is_published for quiz in quizzes))
        self.assertTrue(all(quiz.questions.exists() for quiz in quizzes))
        # Every question needs exactly one correct choice or it cannot be scored.
        for question in Question.objects.all():
            self.assertEqual(
                question.choices.filter(is_correct=True).count(),
                1,
                msg=f"{question.prompt[:50]} must have one correct choice",
            )
        self.assertTrue(Choice.objects.exists())

    def test_is_idempotent(self):
        run()
        counts = (
            Course.objects.count(),
            CourseFolder.objects.count(),
            Lesson.objects.count(),
            PdfResource.objects.count(),
            TestSeries.objects.count(),
            Quiz.objects.count(),
            Question.objects.count(),
            Choice.objects.count(),
        )

        run()

        self.assertEqual(
            counts,
            (
                Course.objects.count(),
                CourseFolder.objects.count(),
                Lesson.objects.count(),
                PdfResource.objects.count(),
                TestSeries.objects.count(),
                Quiz.objects.count(),
                Question.objects.count(),
                Choice.objects.count(),
            ),
        )

    def test_seed_data_holds_no_media_urls(self):
        """Seeded lessons carry no video URL and every PDF is protected, so the
        public payload can never advertise a link that would 404."""
        run()

        self.assertFalse(Lesson.objects.exclude(video_url="").exists())
        self.assertTrue(PdfResource.objects.exists())
        self.assertFalse(PdfResource.objects.filter(is_protected=False).exists())

    def test_clear_removes_only_demo_rows(self):
        run()
        keep = Course.objects.create(
            title="A real batch",
            slug="a-real-batch",
            subject="Physics",
            pricing_mode=Course.PricingMode.FREE,
            price=Decimal("0.00"),
            is_published=True,
        )

        run("--clear")

        self.assertTrue(Course.objects.filter(pk=keep.pk).exists())
        self.assertFalse(Course.objects.filter(slug__startswith="demo-").exists())
        self.assertFalse(TestSeries.objects.filter(slug__startswith="demo-").exists())
        self.assertFalse(Quiz.objects.exists())
        self.assertFalse(Question.objects.exists())

    def test_anonymous_api_lists_the_seeded_tests_with_their_papers(self):
        run()
        client = APIClient()

        response = client.get("/api/quizzes/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["count"], 4)

        first = payload["results"][0]
        self.assertTrue(first["has_access"])
        self.assertGreater(first["question_count"], 0)
        self.assertEqual(len(first["questions"]), first["question_count"])
        self.assertTrue(first["series_title"])
        self.assertEqual(first["attempt_count"], 0)
        # The correct answer never travels in a sit-able paper.
        for question in first["questions"]:
            self.assertNotIn("is_correct", question["choices"][0])

    def test_anonymous_api_lists_the_seeded_catalogue(self):
        run()
        client = APIClient()

        response = client.get("/api/courses/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["count"], 5)

        course = payload["results"][0]
        self.assertIn("quiz_count", course)
        self.assertGreater(course["lesson_count"], 0)

    def test_catalogue_can_be_resolved_by_slug(self):
        """The batch page addresses a course by slug before it has an id."""
        run()
        client = APIClient()
        paid = Course.objects.filter(pricing_mode=Course.PricingMode.PAID).first()

        response = client.get("/api/courses/", {"slug": paid.slug})

        self.assertEqual(response.status_code, 200)
        rows = response.json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], paid.pk)

    def test_paid_course_media_stays_locked(self):
        run()
        client = APIClient()
        paid = Course.objects.filter(pricing_mode=Course.PricingMode.PAID).first()

        response = client.get(f"/api/courses/{paid.pk}/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["has_access"])
        media = [
            lesson["video_url"]
            for folder in body["folders"]
            for lesson in folder["lessons"]
        ]
        self.assertTrue(all(url is None for url in media))
