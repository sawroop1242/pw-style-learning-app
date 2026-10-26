"""Regression tests for the access-control and data-integrity fixes.

Each test documents a defect that existed before this pass, so a future change
that reintroduces it fails here rather than in production.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import (
    AccessCode,
    AttemptAnswer,
    Choice,
    Course,
    CourseAccessGrant,
    CourseFolder,
    Lesson,
    PdfResource,
    Progress,
    Question,
    Quiz,
    QuizAttempt,
)
from courses.models.access import (
    generate_access_code,
    hash_access_code,
    legacy_hash_access_code,
)

User = get_user_model()


class ApiTestMixin:
    @classmethod
    def setUpTestData(cls):
        def make_user(name, role=Role.STUDENT, staff=False):
            user = User.objects.create_user(
                username=name,
                email=f"{name}@example.com",
                password="TestPass123!",
                is_staff=staff,
            )
            user.profile.role = role
            user.profile.save()
            return user

        cls.main_admin = make_user("main", Role.MAIN_ADMIN, staff=True)
        cls.sub_admin = make_user("sub", Role.SUB_ADMIN, staff=True)
        cls.student = make_user("student")
        cls.grantee = make_user("grantee")

        cls.free_course = Course.objects.create(
            title="Free Course", slug="free-course", owner=cls.sub_admin,
            pricing_mode=Course.PricingMode.FREE, is_published=True,
        )
        cls.paid_course = Course.objects.create(
            title="Paid Course", slug="paid-course", owner=cls.sub_admin,
            pricing_mode=Course.PricingMode.PAID, price=Decimal("499.00"),
            is_published=True,
        )
        CourseAccessGrant.objects.create(
            user=cls.grantee, course=cls.paid_course, granted_by=cls.sub_admin
        )

        cls.free_folder = CourseFolder.objects.create(course=cls.free_course, title="Free Folder")
        cls.paid_folder = CourseFolder.objects.create(course=cls.paid_course, title="Paid Folder")

        cls.free_lesson = Lesson.objects.create(
            course=cls.free_course, folder=cls.free_folder, title="Free Lesson",
            video_url="https://youtu.be/FREEVIDEO", is_published=True,
        )
        cls.paid_lesson = Lesson.objects.create(
            course=cls.paid_course, folder=cls.paid_folder, title="Paid Lesson",
            video_url="https://youtu.be/PAIDVIDEO", is_published=True,
        )
        cls.paid_pdf = PdfResource.objects.create(
            folder=cls.paid_folder, title="Paid PDF",
            file_url="https://example.com/paid.pdf",
            is_published=True, is_protected=True,
        )

        cls.paid_quiz = Quiz.objects.create(
            course=cls.paid_course, title="Paid Test", is_published=True,
            timing_mode=Quiz.TimingMode.TIMED, duration_minutes=30,
        )
        cls.paid_question = Question.objects.create(
            quiz=cls.paid_quiz, prompt="PAID PROMPT", explanation="PAID EXPLANATION"
        )
        cls.paid_choice = Choice.objects.create(
            question=cls.paid_question, text="PAID OPTION A", is_correct=True
        )
        Choice.objects.create(question=cls.paid_question, text="PAID OPTION B")

    def setUp(self):
        cache.clear()

    def anon(self):
        return APIClient(raise_request_exception=False)

    def as_user(self, user):
        client = APIClient(raise_request_exception=False)
        client.force_authenticate(user)
        return client


class PaidContentLeakTests(ApiTestMixin, TestCase):
    """A paid course must never expose its media from a public payload."""

    def test_course_detail_hides_media_from_anonymous(self):
        response = self.anon().get(f"/api/courses/{self.paid_course.id}/")
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(body["has_access"])
        self.assertNotIn("PAIDVIDEO", str(body))
        self.assertNotIn("paid.pdf", str(body))

    def test_course_detail_hides_media_from_student_without_grant(self):
        response = self.as_user(self.student).get(f"/api/courses/{self.paid_course.id}/")
        body = response.json()
        self.assertFalse(body["has_access"])
        self.assertNotIn("PAIDVIDEO", str(body))
        self.assertNotIn("paid.pdf", str(body))

    def test_course_detail_reveals_media_to_grantee(self):
        response = self.as_user(self.grantee).get(f"/api/courses/{self.paid_course.id}/")
        body = response.json()
        self.assertTrue(body["has_access"])
        self.assertIn("PAIDVIDEO", str(body))
        self.assertIn("paid.pdf", str(body))

    def test_course_detail_reveals_media_to_owner(self):
        response = self.as_user(self.sub_admin).get(f"/api/courses/{self.paid_course.id}/")
        self.assertIn("PAIDVIDEO", str(response.json()))

    def test_free_course_media_stays_public(self):
        response = self.anon().get(f"/api/courses/{self.free_course.id}/")
        self.assertIn("FREEVIDEO", str(response.json()))

    def test_lesson_list_excludes_paid_course_for_anonymous(self):
        response = self.anon().get("/api/lessons/")
        titles = [lesson["title"] for lesson in response.json()["results"]]
        self.assertIn("Free Lesson", titles)
        self.assertNotIn("Paid Lesson", titles)


class PaidQuizLeakTests(ApiTestMixin, TestCase):
    def test_quiz_list_hides_questions_for_paid_course(self):
        response = self.anon().get("/api/quizzes/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("PAID PROMPT", response.content.decode())

    def test_quiz_list_returns_questions_to_grantee(self):
        response = self.as_user(self.grantee).get("/api/quizzes/")
        self.assertIn("PAID PROMPT", response.content.decode())

    def test_quiz_detail_hides_explanation_always(self):
        response = self.as_user(self.grantee).get(f"/api/quizzes/{self.paid_quiz.id}/")
        self.assertNotIn("PAID EXPLANATION", response.content.decode())

    def test_quiz_list_question_count_present_without_questions(self):
        response = self.anon().get("/api/quizzes/")
        payload = response.json()["results"]
        if payload:
            self.assertEqual(payload[0]["question_count"], 1)
            self.assertEqual(payload[0]["questions"], [])


class StartAttemptTests(ApiTestMixin, TestCase):
    def test_anonymous_start_on_a_paid_quiz_is_forbidden(self):
        """A guest may sit a public paper, never a paid one.

        The guest path was added so that sitting a test needs no account; it
        must not become a way around the grant check.
        """
        response = self.anon().post(
            "/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(QuizAttempt.objects.filter(guest_token_hash__gt="").exists())

    def test_student_without_grant_is_forbidden(self):
        response = self.as_user(self.student).post(
            "/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(QuizAttempt.objects.filter(user=self.student).exists())

    def test_grantee_can_start_and_gets_snapshot(self):
        response = self.as_user(self.grantee).post(
            "/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        attempt = QuizAttempt.objects.get(user=self.grantee)
        self.assertEqual(attempt.question_order, [self.paid_question.id])
        self.assertEqual(attempt.answers.count(), 1)
        self.assertTrue(attempt.rules_snapshot)

    def test_restart_resumes_instead_of_creating_second_attempt(self):
        client = self.as_user(self.grantee)
        first = client.post("/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json")
        second = client.post("/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json")
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(QuizAttempt.objects.filter(user=self.grantee).count(), 1)

    def test_attempt_limit_enforced(self):
        self.paid_quiz.attempt_limit = 1
        self.paid_quiz.save(update_fields=["attempt_limit"])
        client = self.as_user(self.grantee)
        client.post("/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json")
        QuizAttempt.objects.filter(user=self.grantee).update(status=QuizAttempt.Status.SUBMITTED)
        response = client.post("/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_non_integer_quiz_id_is_a_400(self):
        response = self.as_user(self.grantee).post(
            "/api/quizzes/start/", {"quiz_id": "abc"}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class AttemptTamperTests(ApiTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.attempt = QuizAttempt.objects.create(
            user=self.grantee, quiz=self.paid_quiz,
            question_order=[self.paid_question.id],
        )

    def test_attempt_update_routes_are_not_exposed(self):
        client = self.as_user(self.grantee)
        url = f"/api/quiz-attempts/{self.attempt.id}/"
        self.assertEqual(client.put(url, {"status": "submitted"}, format="json").status_code, 405)
        self.assertEqual(client.patch(url, {"status": "submitted"}, format="json").status_code, 405)
        self.assertEqual(client.delete(url).status_code, 405)

    def test_attempt_create_route_is_not_exposed(self):
        response = self.as_user(self.grantee).post(
            "/api/quiz-attempts/", {"quiz": self.paid_quiz.id}, format="json"
        )
        self.assertEqual(response.status_code, 405)

    def test_other_students_attempt_is_not_visible(self):
        other = self.as_user(self.student)
        response = other.get(f"/api/quiz-attempts/{self.attempt.id}/")
        self.assertEqual(response.status_code, 404)


class GradingTests(ApiTestMixin, TestCase):
    def test_autosaved_answer_survives_empty_submit(self):
        client = self.as_user(self.grantee)
        attempt_id = client.post(
            "/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json"
        ).json()["id"]
        client.post(
            f"/api/quiz-attempts/{attempt_id}/autosave/",
            {"question_id": self.paid_question.id, "choice_ids": [self.paid_choice.id]},
            format="json",
        )
        response = client.post(
            f"/api/quiz-attempts/{attempt_id}/submit/", {"answers": []}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        attempt = QuizAttempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.score, Decimal("1.00"))
        self.assertEqual(attempt.max_score, Decimal("1.00"))

    def test_max_score_covers_unanswered_questions(self):
        second = Question.objects.create(
            quiz=self.paid_quiz, prompt="SECOND", position=2
        )
        Choice.objects.create(question=second, text="right", is_correct=True)
        client = self.as_user(self.grantee)
        attempt_id = client.post(
            "/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json"
        ).json()["id"]
        client.post(
            f"/api/quiz-attempts/{attempt_id}/submit/",
            {"answers": [{"question_id": self.paid_question.id,
                          "choice_ids": [self.paid_choice.id]}]},
            format="json",
        )
        attempt = QuizAttempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.score, Decimal("1.00"))
        self.assertEqual(attempt.max_score, Decimal("2.00"))

    def test_wrong_answer_applies_negative_marks(self):
        self.paid_quiz.negative_marks_per_wrong = Decimal("0.25")
        self.paid_quiz.save(update_fields=["negative_marks_per_wrong"])
        wrong = Choice.objects.get(question=self.paid_question, text="PAID OPTION B")
        client = self.as_user(self.grantee)
        attempt_id = client.post(
            "/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json"
        ).json()["id"]
        client.post(
            f"/api/quiz-attempts/{attempt_id}/submit/",
            {"answers": [{"question_id": self.paid_question.id, "choice_ids": [wrong.id]}]},
            format="json",
        )
        attempt = QuizAttempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.score, Decimal("0.00"))  # floored at zero
        self.assertEqual(attempt.max_score, Decimal("1.00"))

    def test_double_submit_is_rejected(self):
        client = self.as_user(self.grantee)
        attempt_id = client.post(
            "/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json"
        ).json()["id"]
        first = client.post(
            f"/api/quiz-attempts/{attempt_id}/submit/", {"answers": []}, format="json"
        )
        second = client.post(
            f"/api/quiz-attempts/{attempt_id}/submit/", {"answers": []}, format="json"
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)

    def test_choice_from_another_question_is_rejected(self):
        other_question = Question.objects.create(quiz=self.paid_quiz, prompt="OTHER")
        foreign = Choice.objects.create(question=other_question, text="foreign")
        client = self.as_user(self.grantee)
        attempt_id = client.post(
            "/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json"
        ).json()["id"]
        response = client.post(
            f"/api/quiz-attempts/{attempt_id}/submit/",
            {"answers": [{"question_id": self.paid_question.id,
                          "choice_ids": [foreign.id]}]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class ResultReleaseTests(ApiTestMixin, TestCase):
    def _submitted_attempt(self, policy, **quiz_fields):
        for field, value in quiz_fields.items():
            setattr(self.paid_quiz, field, value)
        self.paid_quiz.result_release_policy = policy
        self.paid_quiz.save()
        attempt = QuizAttempt.objects.create(
            user=self.grantee, quiz=self.paid_quiz, status=QuizAttempt.Status.SUBMITTED,
            submitted_at=timezone.now(), score=Decimal("1"), max_score=Decimal("1"),
            question_order=[self.paid_question.id],
        )
        AttemptAnswer.objects.create(
            attempt=attempt, question=self.paid_question, answered=True
        ).selected_choices.set([self.paid_choice])
        return attempt

    def test_immediate_policy_releases_on_submit(self):
        client = self.as_user(self.grantee)
        attempt_id = client.post(
            "/api/quizzes/start/", {"quiz_id": self.paid_quiz.id}, format="json"
        ).json()["id"]
        client.post(
            f"/api/quiz-attempts/{attempt_id}/submit/",
            {"answers": [{"question_id": self.paid_question.id,
                          "choice_ids": [self.paid_choice.id]}]},
            format="json",
        )
        response = client.get(f"/api/quiz-attempts/{attempt_id}/result/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["correct_count"], 1)
        self.assertEqual(payload["answers_detail"][0]["correct_choices"][0]["id"],
                         self.paid_choice.id)

    def test_after_close_is_not_released_early(self):
        attempt = self._submitted_attempt(
            Quiz.ResultReleasePolicy.AFTER_CLOSE,
            closes_at=timezone.now() + timezone.timedelta(days=1),
        )
        response = self.as_user(self.grantee).get(f"/api/quiz-attempts/{attempt.id}/result/")
        self.assertEqual(response.status_code, 403)

    def test_after_close_releases_once_closed(self):
        attempt = self._submitted_attempt(
            Quiz.ResultReleasePolicy.AFTER_CLOSE,
            closes_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        response = self.as_user(self.grantee).get(f"/api/quiz-attempts/{attempt.id}/result/")
        self.assertEqual(response.status_code, 200)
        attempt.refresh_from_db()
        self.assertIsNotNone(attempt.result_released_at)

    def test_unreleased_result_never_includes_answers(self):
        attempt = self._submitted_attempt(Quiz.ResultReleasePolicy.MANUAL)
        response = self.as_user(self.grantee).get(f"/api/quiz-attempts/{attempt.id}/")
        self.assertNotIn("PAID EXPLANATION", response.content.decode())


class ProgressTests(ApiTestMixin, TestCase):
    def test_duplicate_progress_updates_instead_of_erroring(self):
        client = self.as_user(self.student)
        first = client.post("/api/progress/", {"lesson": self.free_lesson.id, "completed": True},
                            format="json")
        second = client.post("/api/progress/", {"lesson": self.free_lesson.id, "completed": False},
                             format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["completed"])
        self.assertEqual(Progress.objects.filter(user=self.student).count(), 1)

    def test_progress_on_draft_lesson_is_rejected(self):
        draft = Lesson.objects.create(course=self.free_course, title="DRAFT TITLE")
        response = self.as_user(self.student).post(
            "/api/progress/", {"lesson": draft.id}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("DRAFT TITLE", response.content.decode())

    def test_progress_cannot_be_repointed_at_another_lesson(self):
        client = self.as_user(self.student)
        created = client.post("/api/progress/", {"lesson": self.free_lesson.id}, format="json")
        response = client.patch(
            f"/api/progress/{created.json()['id']}/",
            {"lesson": self.paid_lesson.id}, format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Paid Lesson", response.content.decode())

    def test_progress_on_unpurchased_course_is_rejected(self):
        response = self.as_user(self.student).post(
            "/api/progress/", {"lesson": self.paid_lesson.id}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class AccessCodeRedemptionTests(ApiTestMixin, TestCase):
    def _code(self, raw=None, **kwargs):
        raw = raw or generate_access_code()
        code = AccessCode.objects.create(
            course=self.paid_course,
            code_hash=hash_access_code(raw),
            created_by=self.sub_admin,
            **kwargs,
        )
        return raw, code

    def test_valid_code_creates_grant(self):
        raw, _ = self._code()
        response = self.as_user(self.student).post(
            "/api/access-codes/redeem/",
            {"code": raw, "course_id": self.paid_course.id}, format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            CourseAccessGrant.objects.filter(user=self.student, course=self.paid_course).exists()
        )

    def test_redemption_is_case_insensitive_and_trimmed(self):
        raw, _ = self._code()
        response = self.as_user(self.student).post(
            "/api/access-codes/redeem/",
            {"code": f"  {raw.lower()}  ", "course_id": self.paid_course.id}, format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_second_redemption_is_rejected(self):
        raw, code = self._code(max_uses=2)
        client = self.as_user(self.student)
        client.post("/api/access-codes/redeem/",
                    {"code": raw, "course_id": self.paid_course.id}, format="json")
        response = client.post("/api/access-codes/redeem/",
                               {"code": raw, "course_id": self.paid_course.id}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_exhausted_code_is_rejected(self):
        raw, code = self._code(max_uses=1)
        AccessCode.objects.filter(pk=code.pk).update(uses_count=1)
        response = self.as_user(self.student).post(
            "/api/access-codes/redeem/",
            {"code": raw, "course_id": self.paid_course.id}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_expired_code_is_rejected(self):
        raw, _ = self._code(expires_at=timezone.now() - timezone.timedelta(hours=1))
        response = self.as_user(self.student).post(
            "/api/access-codes/redeem/",
            {"code": raw, "course_id": self.paid_course.id}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_legacy_hash_still_redeems_and_is_upgraded(self):
        raw = generate_access_code()
        code = AccessCode.objects.create(
            course=self.paid_course,
            code_hash=legacy_hash_access_code(raw),
            created_by=self.sub_admin,
        )
        response = self.as_user(self.student).post(
            "/api/access-codes/redeem/",
            {"code": raw, "course_id": self.paid_course.id}, format="json",
        )
        self.assertEqual(response.status_code, 201)
        code.refresh_from_db()
        self.assertTrue(code.code_hash.startswith("v2$"))

    def test_anonymous_redemption_is_rejected(self):
        raw, _ = self._code()
        response = self.anon().post(
            "/api/access-codes/redeem/",
            {"code": raw, "course_id": self.paid_course.id}, format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_code_for_another_course_is_rejected(self):
        raw, _ = self._code()
        response = self.as_user(self.student).post(
            "/api/access-codes/redeem/",
            {"code": raw, "course_id": self.free_course.id}, format="json",
        )
        self.assertEqual(response.status_code, 400)


class StaffContentTests(ApiTestMixin, TestCase):
    def test_lesson_can_be_created_without_a_video(self):
        response = self.as_user(self.sub_admin).post(
            "/api/staff/lessons/",
            {"course": self.free_course.id, "folder": self.free_folder.id, "title": "New Lesson"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_lesson_in_folder_from_another_course_is_rejected(self):
        response = self.as_user(self.sub_admin).post(
            "/api/staff/lessons/",
            {"course": self.free_course.id, "folder": self.paid_folder.id, "title": "Bad"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_lesson_with_disallowed_video_host_is_rejected(self):
        response = self.as_user(self.sub_admin).post(
            "/api/staff/lessons/",
            {"course": self.free_course.id, "title": "Bad", "video_url": "https://evil.example/x.mp4"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_sub_admin_cannot_create_lesson_in_foreign_course(self):
        foreign_owner = User.objects.create_user(
            username="other", email="other@example.com", password="TestPass123!"
        )
        foreign_owner.profile.role = Role.SUB_ADMIN
        foreign_owner.profile.save()
        foreign_course = Course.objects.create(
            title="Foreign", slug="foreign", owner=foreign_owner, is_published=True
        )
        response = self.as_user(self.sub_admin).post(
            "/api/staff/lessons/",
            {"course": foreign_course.id, "title": "Nope"}, format="json",
        )
        self.assertEqual(response.status_code, 403)


class QueryBudgetTests(ApiTestMixin, TestCase):
    def test_quiz_list_query_count_is_bounded(self):
        for index in range(5):
            quiz = Quiz.objects.create(
                course=self.free_course, title=f"Free Quiz {index}", is_published=True
            )
            question = Question.objects.create(quiz=quiz, prompt=f"Q{index}")
            Choice.objects.create(question=question, text="a", is_correct=True)
            Choice.objects.create(question=question, text="b")
        with CaptureQueriesContext(connection) as ctx:
            response = self.as_user(self.student).get("/api/quizzes/")
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(ctx.captured_queries), 6)

    def test_progress_list_query_count_is_bounded(self):
        client = self.as_user(self.student)
        for index in range(10):
            lesson = Lesson.objects.create(
                course=self.free_course, title=f"Lesson {index}", is_published=True
            )
            Progress.objects.create(user=self.student, lesson=lesson)
        with CaptureQueriesContext(connection) as ctx:
            response = client.get("/api/progress/")
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(ctx.captured_queries), 6)
