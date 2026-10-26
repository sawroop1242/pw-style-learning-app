"""Guest test attempts, the public announcement feed and the PDF library.

The front end reads nothing but the API, so the three things a page needed and
the API did not yet serve live here: announcements, downloadable notes, and a
test window a visitor can actually sit without an account.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import (
    Choice,
    CommunityPost,
    Course,
    CourseFolder,
    PdfResource,
    Question,
    Quiz,
    QuizAttempt,
)

User = get_user_model()


class GuestAttemptTestData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="TestPass123!"
        )
        cls.admin.profile.role = Role.MAIN_ADMIN
        cls.admin.profile.save()

        cls.free_course = Course.objects.create(
            title="Free Batch", slug="free-batch", owner=cls.admin,
            pricing_mode=Course.PricingMode.FREE, is_published=True,
        )
        cls.folder = CourseFolder.objects.create(course=cls.free_course, title="Week 1")

        cls.quiz = Quiz.objects.create(
            course=cls.free_course, title="Open Mock", is_published=True,
            timing_mode=Quiz.TimingMode.TIMED, duration_minutes=30,
        )
        cls.question = Question.objects.create(
            quiz=cls.quiz, prompt="2 + 2 = ?", position=1
        )
        cls.right = Choice.objects.create(
            question=cls.question, text="4", is_correct=True, position=1
        )
        cls.wrong = Choice.objects.create(
            question=cls.question, text="5", is_correct=False, position=2
        )

        cls.paid_course = Course.objects.create(
            title="Paid Batch", slug="paid-batch", owner=cls.admin,
            pricing_mode=Course.PricingMode.PAID, price=499, is_published=True,
        )
        cls.paid_quiz = Quiz.objects.create(
            course=cls.paid_course, title="Paid Mock", is_published=True
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient(raise_request_exception=False)


class GuestAttemptTests(GuestAttemptTestData, TestCase):
    def start(self, quiz=None, token=None):
        extra = {"HTTP_X_ATTEMPT_TOKEN": token} if token else {}
        return self.client.post(
            "/api/quizzes/start/",
            {"quiz_id": (quiz or self.quiz).id},
            format="json",
            **extra,
        )

    def test_a_visitor_can_start_without_an_account(self):
        response = self.start()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["guest_token"])
        attempt = QuizAttempt.objects.get(pk=body["id"])
        self.assertIsNone(attempt.user)
        self.assertTrue(attempt.guest_token_hash)
        # The plaintext token is never stored.
        self.assertNotEqual(attempt.guest_token_hash, body["guest_token"])

    def test_the_paper_is_still_scored_on_the_server(self):
        token = self.start().json()["guest_token"]
        attempt_id = QuizAttempt.objects.get().id
        saved = self.client.post(
            f"/api/quiz-attempts/{attempt_id}/autosave/",
            {"question_id": self.question.id, "choice_ids": [self.right.id]},
            format="json",
            HTTP_X_ATTEMPT_TOKEN=token,
        )
        self.assertEqual(saved.status_code, 200)

        result = self.client.post(
            f"/api/quiz-attempts/{attempt_id}/submit/",
            {"answers": []},
            format="json",
            HTTP_X_ATTEMPT_TOKEN=token,
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(float(result.json()["score"]), float(self.quiz.marks_per_question))

    def test_the_token_resumes_instead_of_opening_a_second_attempt(self):
        token = self.start().json()["guest_token"]
        again = self.start(token=token)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(QuizAttempt.objects.count(), 1)
        self.assertNotIn("guest_token", again.json())

    def test_a_stranger_without_the_token_cannot_read_the_attempt(self):
        attempt_id = self.start().json()["id"]
        for url in (
            f"/api/quiz-attempts/{attempt_id}/",
            f"/api/quiz-attempts/{attempt_id}/result/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_a_wrong_token_is_refused(self):
        attempt_id = self.start().json()["id"]
        response = self.client.post(
            f"/api/quiz-attempts/{attempt_id}/autosave/",
            {"question_id": self.question.id, "choice_ids": []},
            format="json",
            HTTP_X_ATTEMPT_TOKEN="not-the-token",
        )
        self.assertEqual(response.status_code, 404)

    def test_a_guest_cannot_start_a_paid_paper(self):
        response = self.start(quiz=self.paid_quiz)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_guests_have_no_attempt_history(self):
        self.start()
        response = self.client.get("/api/quiz-attempts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_a_signed_in_learner_still_gets_a_user_attempt(self):
        self.client.force_authenticate(self.admin)
        response = self.start()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("guest_token", response.json())
        self.assertEqual(QuizAttempt.objects.get().user, self.admin)


class CommunityFeedTests(GuestAttemptTestData, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.pinned = CommunityPost.objects.create(
            title="Pinned notice", body="Exam window moved", author=cls.admin,
            is_published=True, is_pinned=True,
        )
        cls.latest = CommunityPost.objects.create(
            title="New PYQ set", body="SSC CGL 2025 added", author=cls.admin,
            is_published=True,
        )
        cls.course_post = CommunityPost.objects.create(
            title="Batch notice", body="Class at 6 PM", author=cls.admin,
            course=cls.free_course, is_published=True,
        )
        cls.draft = CommunityPost.objects.create(
            title="Draft notice", body="Not ready", author=cls.admin, is_published=False
        )

    def test_only_published_posts_are_public(self):
        response = self.client.get("/api/community/")
        self.assertEqual(response.status_code, 200)
        titles = [row["title"] for row in response.json()["results"]]
        self.assertNotIn("Draft notice", titles)
        self.assertEqual(titles[0], "Pinned notice")

    def test_the_feed_carries_no_contact_details(self):
        row = self.client.get("/api/community/").json()["results"][0]
        self.assertEqual(row["author"], "admin")
        self.assertNotIn("email", row)

    def test_a_course_filter_includes_platform_wide_posts(self):
        response = self.client.get(f"/api/community/?course={self.free_course.id}")
        titles = {row["title"] for row in response.json()["results"]}
        self.assertEqual(titles, {"Pinned notice", "New PYQ set", "Batch notice"})

    def test_the_feed_is_read_only(self):
        self.assertEqual(
            self.client.post("/api/community/", {"title": "x"}, format="json").status_code,
            405,
        )


class PdfLibraryTests(GuestAttemptTestData, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.free_pdf = PdfResource.objects.create(
            folder=cls.folder, title="Formula sheet",
            file_url="https://example.com/formula.pdf", is_published=True,
        )
        cls.paid_folder = CourseFolder.objects.create(
            course=cls.paid_course, title="Paid week"
        )
        cls.locked_pdf = PdfResource.objects.create(
            folder=cls.paid_folder, title="Protected notes",
            file_url="https://example.com/secret.pdf",
            is_published=True, is_protected=True,
        )
        cls.draft_pdf = PdfResource.objects.create(
            folder=cls.folder, title="Draft notes",
            file_url="https://example.com/draft.pdf", is_published=False,
        )
        cls.paid_pdf = PdfResource.objects.create(
            folder=cls.paid_folder, title="Paid notes",
            file_url="https://example.com/paid.pdf", is_published=True, is_protected=True,
        )

    def test_published_notes_are_listed_and_drafts_are_not(self):
        response = self.client.get("/api/pdfs/")
        self.assertEqual(response.status_code, 200)
        titles = {row["title"] for row in response.json()["results"]}
        self.assertNotIn("Draft notes", titles)
        self.assertIn("Formula sheet", titles)

    def test_a_protected_file_url_is_withheld_from_a_visitor(self):
        rows = {row["title"]: row for row in self.client.get("/api/pdfs/").json()["results"]}
        self.assertIsNone(rows["Protected notes"]["file_url"])
        self.assertTrue(rows["Protected notes"]["is_locked"])
        self.assertEqual(
            rows["Formula sheet"]["file_url"], "https://example.com/formula.pdf"
        )

    def test_a_course_filter_limits_the_library(self):
        rows = self.client.get(
            f"/api/pdfs/?course={self.paid_course.id}"
        ).json()["results"]
        self.assertEqual(
            sorted(row["title"] for row in rows), ["Paid notes", "Protected notes"]
        )


class CourseAccessFlagTests(GuestAttemptTestData, TestCase):
    def test_free_batches_report_access_and_paid_ones_do_not(self):
        rows = {row["slug"]: row for row in self.client.get("/api/courses/").json()["results"]}
        self.assertTrue(rows["free-batch"]["has_access"])
        self.assertFalse(rows["paid-batch"]["has_access"])

    def test_mine_returns_only_openable_batches(self):
        response = self.client.get("/api/courses/?mine=1")
        self.assertEqual(
            [row["slug"] for row in response.json()["results"]], ["free-batch"]
        )
