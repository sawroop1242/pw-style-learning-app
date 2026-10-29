"""The features this run connected to an endpoint.

Four screens used to offer something the API could not answer:

* the batch page's Faculty panel, which had no model behind it;
* the exam window's "Report a question", which collected a reason and threw it
  away with the autosave payload;
* the top bar's bell, which had no handler at all;
* the attempt history, which showed "Test #5" because the payload carried only
  an id.

Each test here pins the contract the screen now depends on, including what a
caller may *not* do.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import (
    Choice,
    CommunityPost,
    Course,
    CourseFaculty,
    CourseFolder,
    Lesson,
    NotificationRead,
    Question,
    QuestionReport,
    Quiz,
    QuizAttempt,
    StudyTask,
)

User = get_user_model()


class ConnectedFeatureData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="provider", email="provider@example.com", password="TestPass123!"
        )
        cls.owner.profile.role = Role.SUB_ADMIN
        cls.owner.profile.save()

        cls.other = User.objects.create_user(
            username="other_provider", password="TestPass123!"
        )
        cls.other.profile.role = Role.SUB_ADMIN
        cls.other.profile.save()

        cls.student = User.objects.create_user(
            username="student", email="student@example.com", password="TestPass123!"
        )

        cls.course = Course.objects.create(
            title="Open Batch",
            slug="open-batch",
            owner=cls.owner,
            pricing_mode=Course.PricingMode.FREE,
            is_published=True,
        )
        cls.folder = CourseFolder.objects.create(course=cls.course, title="Week 1")
        cls.lesson = Lesson.objects.create(
            course=cls.course, folder=cls.folder, title="Vectors", is_published=True
        )
        cls.quiz = Quiz.objects.create(
            course=cls.course,
            title="Open Mock",
            is_published=True,
            timing_mode=Quiz.TimingMode.UNTIMED,
        )
        cls.question = Question.objects.create(
            quiz=cls.quiz, prompt="2 + 2 = ?", position=1, topic="Arithmetic"
        )
        Choice.objects.create(
            question=cls.question, text="4", is_correct=True, position=1
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()


class FacultyTests(ConnectedFeatureData):
    def test_course_detail_lists_its_faculty(self):
        CourseFaculty.objects.create(
            course=self.course, name="Dr. Meera Kulkarni", subject="Physics", position=1
        )
        CourseFaculty.objects.create(
            course=self.course, name="Anil Bhatt", subject="Mathematics", position=2
        )

        response = self.client.get(f"/api/courses/{self.course.id}/")

        self.assertEqual(response.status_code, 200)
        names = [row["name"] for row in response.json()["faculty"]]
        self.assertEqual(names, ["Dr. Meera Kulkarni", "Anil Bhatt"])

    def test_a_batch_without_faculty_returns_an_empty_list(self):
        response = self.client.get(f"/api/courses/{self.course.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["faculty"], [])

    def test_the_catalogue_page_does_not_fan_out(self):
        """Six rows must cost the same number of queries as one.

        The counters used to come from `lessons.count`/`folders.count`, which
        re-queries per row and ignores the annotation the viewset computed.
        """
        for index in range(5):
            Course.objects.create(
                title=f"Batch {index}",
                slug=f"batch-{index}",
                owner=self.owner,
                pricing_mode=Course.PricingMode.FREE,
                is_published=True,
            )
        CourseFaculty.objects.create(course=self.course, name="Dr. Meera Kulkarni")

        with self.assertNumQueries(2):  # one count + one annotated page
            response = self.client.get("/api/courses/?page_size=6")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 6)
        # Faculty stay off the grid payload; the batch page asks for them.
        self.assertNotIn("faculty", response.json()["results"][0])

    def test_staff_may_only_list_faculty_on_their_own_courses(self):
        self.client.force_authenticate(self.other)
        response = self.client.post(
            "/api/staff/faculty/",
            {"course": self.course.id, "name": "Someone Else"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_the_owner_can_add_faculty(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            "/api/staff/faculty/",
            {"course": self.course.id, "name": "Dr. Meera Kulkarni", "subject": "Physics"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            CourseFaculty.objects.filter(course=self.course, name="Dr. Meera Kulkarni").exists()
        )


class QuestionReportTests(ConnectedFeatureData):
    def start_guest_attempt(self):
        response = self.client.post("/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json")
        self.assertEqual(response.status_code, 201)
        return response.json()

    def report(self, attempt_id, question_id, token=None, **extra):
        payload = {"attempt": attempt_id, "question": question_id, "reason": "ambiguous"}
        payload.update(extra)
        headers = {"HTTP_X_ATTEMPT_TOKEN": token} if token else {}
        return self.client.post("/api/question-reports/", payload, format="json", **headers)

    def test_a_guest_can_report_a_question_on_their_own_attempt(self):
        started = self.start_guest_attempt()

        response = self.report(
            started["id"], self.question.id, token=started["guest_token"], detail="Two answers match."
        )

        self.assertEqual(response.status_code, 201)
        stored = QuestionReport.objects.get()
        self.assertEqual(stored.reason, "ambiguous")
        self.assertEqual(stored.detail, "Two answers match.")
        self.assertIsNone(stored.user_id)
        self.assertEqual(stored.status, "open")

    def test_reporting_twice_updates_instead_of_duplicating(self):
        started = self.start_guest_attempt()
        first = self.report(started["id"], self.question.id, token=started["guest_token"])
        second = self.report(
            started["id"], self.question.id, token=started["guest_token"], reason="typo"
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(QuestionReport.objects.count(), 1)
        self.assertEqual(QuestionReport.objects.get().reason, "typo")

    def test_a_stranger_without_the_attempt_token_is_refused(self):
        started = self.start_guest_attempt()

        response = self.report(started["id"], self.question.id)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(QuestionReport.objects.exists())

    def test_another_students_token_cannot_report_on_your_attempt(self):
        self.client.force_authenticate(self.student)
        started = self.client.post(
            "/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json"
        ).json()

        self.client.force_authenticate(self.other)
        response = self.report(started["id"], self.question.id)

        self.assertEqual(response.status_code, 403)

    def test_a_question_from_another_paper_is_rejected(self):
        started = self.start_guest_attempt()
        other_quiz = Quiz.objects.create(
            course=self.course, title="Other Mock", is_published=True
        )
        foreign = Question.objects.create(quiz=other_quiz, prompt="Elsewhere?", position=1)

        response = self.report(
            started["id"], foreign.id, token=started["guest_token"]
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("question", response.json())

    def test_a_submitted_attempt_cannot_be_reported(self):
        self.client.force_authenticate(self.student)
        started = self.client.post(
            "/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json"
        ).json()
        submitted = self.client.post(
            f"/api/quiz-attempts/{started['id']}/submit/", {"answers": []}, format="json"
        )
        self.assertEqual(submitted.status_code, 200)

        response = self.report(started["id"], self.question.id)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(QuestionReport.objects.exists())

    def test_the_list_only_shows_the_callers_own_reports(self):
        self.client.force_authenticate(self.student)
        started = self.client.post(
            "/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json"
        ).json()
        self.report(started["id"], self.question.id)
        self.assertEqual(self.client.get("/api/question-reports/").json()["count"], 1)

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/question-reports/").json()["count"], 0)

    def test_a_provider_sees_only_reports_on_papers_they_own(self):
        self.client.force_authenticate(self.student)
        started = self.client.post(
            "/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json"
        ).json()
        self.report(started["id"], self.question.id)

        self.client.force_authenticate(self.owner)
        owned = self.client.get("/api/staff/question-reports/").json()
        self.assertEqual(owned["count"], 1)

        self.client.force_authenticate(self.other)
        other = self.client.get("/api/staff/question-reports/").json()
        self.assertEqual(other["count"], 0)

    def test_a_provider_can_move_a_report_along(self):
        self.client.force_authenticate(self.student)
        started = self.client.post(
            "/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json"
        ).json()
        report_id = self.report(started["id"], self.question.id).json()["id"]

        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            f"/api/staff/question-reports/{report_id}/", {"status": "resolved"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuestionReport.objects.get().status, "resolved")


    def test_a_learner_cannot_mark_their_own_report_resolved(self):
        self.client.force_authenticate(self.student)
        started = self.client.post(
            "/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json"
        ).json()

        response = self.report(
            started["id"], self.question.id, status=QuestionReport.Status.RESOLVED
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(QuestionReport.objects.get().status, "open")


def later_today():
    """A moment that is still today, whenever this suite happens to run.

    ``timezone.now() + 1 hour`` looks like "today" but crosses midnight late in
    the evening, so the inbox — which correctly stops at the end of today —
    drops the task and the test fails for real at 23:00 and passes all day.
    Anchoring to noon keeps the meaning without the cliff.
    """
    return timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)


class NotificationTests(ConnectedFeatureData):
    def announcement(self, title, course=None, published=True):
        return CommunityPost.objects.create(
            title=title,
            body=f"{title} body",
            author=self.owner,
            course=course,
            is_published=published,
        )

    def test_a_guest_sees_published_announcements_only(self):
        self.announcement("Mock this week")
        self.announcement("Draft notice", published=False)

        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        titles = [item["title"] for item in body["results"]]
        self.assertEqual(titles, ["Mock this week"])
        self.assertEqual(body["count"], 1)

    def test_a_task_due_today_appears_for_its_owner_only(self):
        StudyTask.objects.create(
            user=self.student, title="Revise vectors", due_at=later_today()
        )
        StudyTask.objects.create(
            user=self.student, title="Later this month", due_at=timezone.now() + timedelta(days=20)
        )

        self.client.force_authenticate(self.student)
        mine = self.client.get("/api/notifications/").json()
        self.assertEqual([item["title"] for item in mine["results"]], ["Revise vectors"])

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/notifications/").json()["count"], 0)

    def test_a_completed_task_drops_out_of_the_inbox(self):
        task = StudyTask.objects.create(
            user=self.student, title="Revise vectors", due_at=later_today()
        )
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/notifications/").json()["count"], 1)

        self.client.post(f"/api/study-tasks/{task.id}/complete/", {}, format="json")

        self.assertEqual(self.client.get("/api/notifications/").json()["count"], 0)

    def test_a_released_result_links_back_to_the_attempt(self):
        attempt = QuizAttempt.objects.create(
            user=self.student,
            quiz=self.quiz,
            status=QuizAttempt.Status.SUBMITTED,
            score="4.00",
            max_score="4.00",
            result_released_at=timezone.now(),
        )

        self.client.force_authenticate(self.student)
        items = self.client.get("/api/notifications/").json()["results"]

        self.assertEqual(items[0]["kind"], "result")
        self.assertIn(f"attempt={attempt.id}", items[0]["href"])
        self.assertIn("100", items[0]["body"])

    def test_an_announcement_for_a_paid_batch_is_hidden_from_a_guest(self):
        paid = Course.objects.create(
            title="Paid Batch",
            slug="paid-batch",
            owner=self.owner,
            pricing_mode=Course.PricingMode.PAID,
            price=499,
            is_published=True,
        )
        self.announcement("Payment window", course=paid)
        self.announcement("Everyone", course=None)

        titles = [item["title"] for item in self.client.get("/api/notifications/").json()["results"]]

        self.assertEqual(titles, ["Everyone"])

    def test_reading_is_recorded_per_account(self):
        self.announcement("Mock this week")
        self.client.force_authenticate(self.student)
        key = self.client.get("/api/notifications/").json()["results"][0]["id"]

        response = self.client.post("/api/notifications/read/", {"keys": [key]}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread"], 0)
        self.assertTrue(NotificationRead.objects.filter(user=self.student, key=key).exists())

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/notifications/").json()["unread"], 1)

    def test_a_guest_cannot_mark_anything_read(self):
        response = self.client.post(
            "/api/notifications/read/", {"keys": ["announcement:1"]}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_a_malformed_read_payload_is_a_400(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/api/notifications/read/", {"keys": "not-a-list"}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class AttemptPayloadTests(ConnectedFeatureData):
    def test_an_attempt_carries_the_paper_title(self):
        self.client.force_authenticate(self.student)
        self.client.post("/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json")

        row = self.client.get("/api/quiz-attempts/").json()["results"][0]

        self.assertEqual(row["quiz_title"], "Open Mock")



class LessonNoteAndProgressTests(ConnectedFeatureData):
    """The learning loop the player drives: open a lesson, write a note on it."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.student)

    def test_progress_can_be_asked_about_one_lesson(self):
        other = Lesson.objects.create(
            course=self.course, title="Momentum", is_published=True
        )
        self.client.post("/api/progress/", {"lesson": self.lesson.id}, format="json")
        self.client.post("/api/progress/", {"lesson": other.id, "completed": True}, format="json")

        response = self.client.get(f"/api/progress/?lesson={self.lesson.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertFalse(response.json()["results"][0]["completed"])

    def test_progress_on_an_unknown_lesson_is_ignored_not_a_500(self):
        response = self.client.get("/api/progress/?lesson=abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2 - 2)  # nothing filtered out of an empty set

    def test_completing_a_lesson_updates_the_same_row(self):
        opened = self.client.post("/api/progress/", {"lesson": self.lesson.id}, format="json")
        response = self.client.post(
            "/api/progress/", {"lesson": self.lesson.id, "completed": True}, format="json"
        )

        # Created once, then updated in place: 201 opens, 200 completes.
        self.assertEqual(opened.status_code, 201)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["completed"])
        self.assertEqual(response.json()["lesson_title"], "Vectors")
        from courses.models import Progress

        self.assertEqual(Progress.objects.filter(user=self.student).count(), 1)

    def test_notes_can_be_asked_for_one_lesson(self):
        other = Lesson.objects.create(
            course=self.course, title="Momentum", is_published=True
        )
        self.client.post(
            "/api/notes/", {"lesson": self.lesson.id, "title": "Vectors", "body": "a·b"}, format="json"
        )
        self.client.post(
            "/api/notes/", {"lesson": other.id, "title": "Momentum", "body": "p=mv"}, format="json"
        )

        response = self.client.get(f"/api/notes/?lesson={self.lesson.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["lesson_title"], "Vectors")

    def test_a_note_cannot_be_attached_to_a_draft_lesson(self):
        draft = Lesson.objects.create(
            course=self.course, title="Unpublished", is_published=False
        )

        response = self.client.post(
            "/api/notes/", {"lesson": draft.id, "title": "Sneaky", "body": "x"}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("lesson", response.json())

    def test_a_note_cannot_be_attached_to_a_lesson_in_a_paid_batch(self):
        paid = Course.objects.create(
            title="Paid Batch",
            slug="paid-batch",
            owner=self.owner,
            pricing_mode=Course.PricingMode.PAID,
            price=499,
            is_published=True,
        )
        locked = Lesson.objects.create(course=paid, title="Locked lesson", is_published=True)

        response = self.client.post(
            "/api/notes/", {"lesson": locked.id, "title": "Sneaky", "body": "x"}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("lesson", response.json())


class LessonVideoTests(ConnectedFeatureData):
    """One real embed URL, served where a learner may watch it and withheld
    everywhere else. The difference is the grant, never the media."""

    VIDEO = "https://embed.vcdn.me/embed/28c4af9f-d817-460a-80ab-9a09f8c47c69"

    def setUp(self):
        super().setUp()
        # A paid batch, so the same lesson has both states to compare.
        self.paid = Course.objects.create(
            title="Paid Batch",
            slug="paid-batch",
            owner=self.owner,
            pricing_mode=Course.PricingMode.PAID,
            price=499,
            is_published=True,
        )
        self.paid_lesson = Lesson.objects.create(
            course=self.paid,
            title="Paid recording",
            video_url=self.VIDEO,
            is_published=True,
        )
        self.lesson.video_url = self.VIDEO
        self.lesson.save(update_fields=["video_url"])

    def test_a_free_lesson_serves_its_video_to_a_guest(self):
        response = self.client.get(f"/api/lessons/{self.lesson.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["video_url"], self.VIDEO)
        self.assertFalse(response.json()["is_locked"])

    def test_a_paid_lesson_withholds_the_same_url_from_a_guest(self):
        response = self.client.get(f"/api/lessons/{self.paid_lesson.id}/")

        # Either it is not listed at all (404) or it is listed without a URL;
        # what must never happen is the URL coming back to a non-grantee.
        if response.status_code == 200:
            self.assertFalse(response.json().get("video_url"))

    def test_a_paid_lesson_serves_the_url_once_the_batch_is_granted(self):
        from courses.models import CourseAccessGrant

        CourseAccessGrant.objects.create(
            user=self.student, course=self.paid, granted_by=self.owner
        )
        self.client.force_authenticate(self.student)

        response = self.client.get(f"/api/lessons/{self.paid_lesson.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["video_url"], self.VIDEO)

    def test_the_embed_host_is_accepted_and_other_hosts_are_not(self):
        from courses.serializers import validate_video_url
        from rest_framework import serializers as drf

        self.assertEqual(validate_video_url(self.VIDEO), self.VIDEO)

        for bad in (
            "https://evil.example/embed/x",
            "http://embed.vcdn.me/embed/28c4af9f",
            "javascript:alert(1)",
        ):
            with self.assertRaises(drf.ValidationError):
                validate_video_url(bad)
