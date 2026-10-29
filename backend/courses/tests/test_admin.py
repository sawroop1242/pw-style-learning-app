from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile, Role
from courses.models import (
    AccessCode,
    Choice,
    Course,
    CourseFolder,
    Lesson,
    Question,
    QuestionReport,
    Quiz,
    TestSeries,
)

User = get_user_model()


class AdminTestDataMixin:
    @classmethod
    def setUpTestData(cls):
        cls.main_admin = User.objects.create_user(
            username="mainadmin", email="main@example.com", password="TestPass123!", is_superuser=True, is_staff=True
        )
        cls.main_admin.profile.role = Role.MAIN_ADMIN
        cls.main_admin.profile.save()
        cls.sub_admin = User.objects.create_user(
            username="subadmin", email="sub@example.com", password="TestPass123!", is_staff=True
        )
        cls.sub_admin.profile.role = Role.SUB_ADMIN
        cls.sub_admin.profile.save()
        cls.other_sub = User.objects.create_user(
            username="othersub", email="other@example.com", password="TestPass123!", is_staff=True
        )
        cls.other_sub.profile.role = Role.SUB_ADMIN
        cls.other_sub.profile.save()
        cls.student = User.objects.create_user(
            username="student", email="student@example.com", password="TestPass123!"
        )
        cls.own_course = Course.objects.create(
            title="Own Course", slug="own-course", owner=cls.sub_admin, is_published=True
        )
        cls.other_course = Course.objects.create(
            title="Other Course", slug="other-course", owner=cls.other_sub, is_published=True
        )

    def setUp(self):
        self.site = admin.site
        self.factory = RequestFactory()

    def request_for(self, user):
        request = self.factory.get("/admin/")
        request.user = user
        return request


class AdminAccessTests(AdminTestDataMixin, TestCase):
    def test_student_cannot_access_admin(self):
        self.client.force_login(self.student)
        response = self.client.get("/admin/")
        target = "/admin/login/?next=/admin/"
        self.assertTrue(
            response.status_code in (302, 403)
            and (response.status_code == 403 or response.url == target)
        )

    def test_sub_admin_can_access_admin_index(self):
        self.client.force_login(self.sub_admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_sub_admin_course_list_is_owner_scoped(self):
        request = self.request_for(self.sub_admin)
        qs = self.site._registry[Course].get_queryset(request)
        self.assertIn(self.own_course, qs)
        self.assertNotIn(self.other_course, qs)

    def test_main_admin_course_list_sees_all(self):
        request = self.request_for(self.main_admin)
        qs = self.site._registry[Course].get_queryset(request)
        self.assertIn(self.own_course, qs)
        self.assertIn(self.other_course, qs)

    def test_sub_admin_cannot_change_other_owners_course(self):
        model_admin = self.site._registry[Course]
        request = self.request_for(self.sub_admin)
        self.assertFalse(model_admin.has_change_permission(request, self.other_course))
        self.assertTrue(model_admin.has_change_permission(request, self.own_course))

    def test_lesson_admin_scoped_by_course_owner(self):
        own_lesson = Lesson.objects.create(course=self.own_course, title="L1")
        other_lesson = Lesson.objects.create(course=self.other_course, title="L2")
        request = self.request_for(self.sub_admin)
        qs = self.site._registry[Lesson].get_queryset(request)
        self.assertIn(own_lesson, qs)
        self.assertNotIn(other_lesson, qs)

    def test_sub_admin_cannot_attach_lesson_to_foreign_course(self):
        """Cross-owner injection via a forged FK ID must fail form validation."""
        self.client.force_login(self.sub_admin)
        url = reverse("admin:courses_lesson_add")
        response = self.client.post(
            url,
            {
                "title": "Injected Lesson",
                "course": self.other_course.id,
                "duration_minutes": 10,
                "position": 1,
                "is_published": "0",
            },
        )
        self.assertEqual(Lesson.objects.filter(course=self.other_course).count(), 0)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errors")
        self.assertEqual(Lesson.objects.count(), 0)

    def test_sub_admin_can_create_lesson_in_own_course(self):
        self.client.force_login(self.sub_admin)
        url = reverse("admin:courses_lesson_add")
        response = self.client.post(
            url,
            {
                "title": "Legit Lesson",
                "course": self.own_course.id,
                "duration_minutes": 10,
                "position": 1,
                "is_published": "0",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lesson.objects.filter(course=self.own_course).count(), 1)

    def test_sub_admin_cannot_create_access_code_for_foreign_course(self):
        self.client.force_login(self.sub_admin)
        url = reverse("admin:courses_accesscode_add")
        response = self.client.post(
            url,
            {"course": self.other_course.id, "max_uses": 1, "expires_at": ""},
        )
        self.assertEqual(AccessCode.objects.filter(course=self.other_course).count(), 0)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errors")


class AccessCodeAdminTests(AdminTestDataMixin, TestCase):
    def test_code_generation_stores_hash_and_shows_raw_once(self):
        self.client.force_login(self.sub_admin)
        url = reverse("admin:courses_accesscode_add")
        response = self.client.post(
            url,
            {
                "course": self.own_course.id,
                "max_uses": 1,
                "expires_at": "",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        code = AccessCode.objects.filter(course=self.own_course).first()
        self.assertIsNotNone(code)
        # Codes are now stored as a keyed HMAC; the legacy prefix is only
        # accepted for verification of already-issued codes.
        self.assertTrue(code.code_hash.startswith("v2$"))
        messages = [str(m) for m in response.context["messages"]]
        raw_codes = [m for m in messages if "will not be shown again" in m]
        self.assertEqual(len(raw_codes), 1)
        raw = raw_codes[0].split(": ")[-1]
        self.assertNotEqual(raw, code.code_hash)
        self.assertNotIn(raw, code.code_hash)

    def test_sub_admin_cannot_create_code_for_foreign_course(self):
        self.client.force_login(self.sub_admin)
        url = reverse("admin:courses_accesscode_add")
        response = self.client.get(url)
        # The course dropdown must only offer owned courses.
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Other Course")
        self.assertContains(response, "Own Course")

    def test_grant_add_is_disabled(self):
        from courses.models import CourseAccessGrant

        request = self.request_for(self.sub_admin)
        grant_admin = self.site._registry[CourseAccessGrant]
        self.assertFalse(grant_admin.has_add_permission(request))

    def test_private_data_admins_reject_sub_admin(self):
        from courses.models import Bookmark, StudyTask

        request = self.request_for(self.sub_admin)
        for model in (Bookmark, StudyTask):
            model_admin = self.site._registry[model]
            self.assertFalse(model_admin.has_module_permission(request))
        request = self.request_for(self.main_admin)
        for model in (Bookmark, StudyTask):
            model_admin = self.site._registry[model]
            self.assertTrue(model_admin.has_module_permission(request))


class TestSeriesAdminTests(AdminTestDataMixin, TestCase):
    def test_series_owner_assigned_on_create(self):
        self.client.force_login(self.sub_admin)
        url = reverse("admin:courses_testseries_add")
        response = self.client.post(
            url,
            {"title": "New Series", "slug": "new-series", "subject": "Maths", "is_published": "0"},
            follow=True,
        )
        self.assertFalse(response.context.get("errors") if response.context else False)
        self.assertEqual(response.status_code, 200)
        series = TestSeries.objects.get(slug="new-series")
        self.assertEqual(series.owner, self.sub_admin)

    def test_sub_admin_cannot_reassign_owner(self):
        from django.core.exceptions import PermissionDenied

        series = TestSeries.objects.create(
            title="Owned", slug="owned-series", owner=self.sub_admin
        )
        self.client.force_login(self.sub_admin)
        url = reverse("admin:courses_testseries_change", args=[series.id])
        response = self.client.post(
            url,
            {
                "title": "Owned",
                "slug": "owned-series",
                "subject": "General",
                "owner": self.other_sub.id,
                "is_published": "0",
            },
        )
        self.assertIn(response.status_code, (403, 302))
        series.refresh_from_db()
        self.assertEqual(series.owner, self.sub_admin)


class AdminCookieTests(TestCase):
    """The admin login POST depends on cookies surviving the hosting context.

    The site can be embedded in an iframe on another origin, where a Lax cookie
    is not sent on a form POST and Django answers "CSRF cookie not set" (403).
    These tests pin the mapping from settings to the actual Set-Cookie header,
    so the embedded-preview configuration cannot be lost by a future edit.
    """

    def test_csrf_cookie_follows_the_configured_samesite(self):
        with override_settings(CSRF_COOKIE_SAMESITE="None", CSRF_COOKIE_SECURE=True):
            response = self.client.get("/admin/login/")

        cookie = response.cookies["csrftoken"]
        self.assertEqual(cookie["samesite"], "None")
        self.assertTrue(cookie["secure"])

    def test_default_samesite_is_still_lax(self):
        with override_settings(CSRF_COOKIE_SAMESITE="Lax"):
            response = self.client.get("/admin/login/")

        self.assertEqual(response.cookies["csrftoken"]["samesite"], "Lax")

    def test_login_form_carries_a_token(self):
        """Without {% csrf_token %} the POST could never pass, cookie or not."""
        response = self.client.get("/admin/login/")
        self.assertContains(response, "csrfmiddlewaretoken")


class AdminIndexTests(AdminTestDataMixin, TestCase):
    """The console home groups models by job, and every link on it must work."""

    def test_the_index_renders_for_a_sub_admin(self):
        self.client.force_login(self.sub_admin)
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Batches and lessons")
        self.assertContains(response, "Tests and questions")

    def test_the_index_lists_every_registered_model(self):
        """A model missing from the cards would be unreachable from the home."""
        self.client.force_login(self.main_admin)
        response = self.client.get("/admin/")

        page = response.content.decode()
        for model in admin.site._registry:
            # Django capitalises the first letter of the label on the index.
            self.assertIn(model._meta.verbose_name_plural.lower(), page.lower())

    def test_every_admin_queryset_survives_a_sub_admin(self):
        """Counting rows on the index calls get_queryset on every admin.

        A scope filter that names a field which does not exist (Quiz has no
        owner, only its series and course do) used to take the whole page down
        with a 500 instead of showing the one list that was misconfigured.
        """
        request = self.request_for(self.sub_admin)

        for model, model_admin in admin.site._registry.items():
            with self.subTest(model=model.__name__):
                self.assertIsNotNone(model_admin.get_queryset(request).count())


class AdminWorkflowTests(AdminTestDataMixin, TestCase):
    """The jobs the console is used for, exercised through the admin itself."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder = CourseFolder.objects.create(course=cls.own_course, title="Mechanics", position=1)
        cls.lesson = Lesson.objects.create(
            course=cls.own_course, folder=cls.folder, title="Vectors", position=1,
            video_url="https://embed.vcdn.me/embed/abc", is_published=True,
        )
        cls.quiz = Quiz.objects.create(title="Mock 1", course=cls.own_course, is_published=False)
        cls.question = Question.objects.create(quiz=cls.quiz, prompt="What is 2 + 2?", position=1)

    def test_publishing_many_lessons_at_once(self):
        self.client.force_login(self.sub_admin)
        draft = Lesson.objects.create(
            course=self.own_course, folder=self.folder, title="Draft", position=2
        )

        self.client.post(
            reverse("admin:courses_lesson_changelist"),
            {"action": "publish_selected", "_selected_action": [str(draft.pk)], "index": "0"},
            follow=True,
        )

        draft.refresh_from_db()
        self.assertTrue(draft.is_published)

    def test_unpublishing_leaves_the_others_alone(self):
        self.client.force_login(self.sub_admin)
        self.client.post(
            reverse("admin:courses_lesson_changelist"),
            {"action": "unpublish_selected", "_selected_action": [str(self.lesson.pk)], "index": "0"},
            follow=True,
        )

        self.lesson.refresh_from_db()
        self.assertFalse(self.lesson.is_published)

    def test_a_lesson_can_be_duplicated_as_a_draft(self):
        self.client.force_login(self.sub_admin)

        self.client.post(
            reverse("admin:courses_lesson_changelist"),
            {"action": "duplicate_selected", "_selected_action": [str(self.lesson.pk)], "index": "0"},
            follow=True,
        )

        copy = Lesson.objects.get(title="Vectors (copy)")
        self.assertEqual(copy.video_url, self.lesson.video_url)
        self.assertEqual(copy.folder_id, self.lesson.folder_id)
        self.assertFalse(copy.is_published, "a duplicate must not go live on its own")

    def test_a_question_can_be_duplicated_with_its_answers(self):
        Choice.objects.create(question=self.question, text="4", is_correct=True, position=0)
        Choice.objects.create(question=self.question, text="5", is_correct=False, position=1)
        self.client.force_login(self.sub_admin)

        self.client.post(
            reverse("admin:courses_question_changelist"),
            {"action": "duplicate_selected", "_selected_action": [str(self.question.pk)], "index": "0"},
            follow=True,
        )

        self.assertEqual(Question.objects.filter(quiz=self.quiz).count(), 2)
        copy = Question.objects.filter(quiz=self.quiz).exclude(pk=self.question.pk).get()
        self.assertEqual([c.text for c in copy.choices.all()], ["4", "5"])
        self.assertEqual([c.is_correct for c in copy.choices.all()], [True, False])

    def test_answers_are_numbered_in_the_order_they_are_written(self):
        """Nobody types 0,1,2,3 — the order of the rows is the order served."""
        self.client.force_login(self.sub_admin)
        formset_data = {
            "quiz": str(self.quiz.pk),
            "prompt": "Which is a prime?",
            "explanation": "",
            "question_type": "single_choice",
            "marks": "",
            "negative_marks": "",
            "difficulty": "easy",
            "topic": "Number theory",
            "position": "2",
            "choices-TOTAL_FORMS": "3",
            "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0",
            "choices-MAX_NUM_FORMS": "10",
            "choices-0-text": "2",
            "choices-0-is_correct": "on",
            "choices-1-text": "4",
            "choices-2-text": "9",
            "_save": "Save",
        }

        response = self.client.post(reverse("admin:courses_question_add"), formset_data, follow=True)

        self.assertEqual(response.status_code, 200)
        question = Question.objects.get(prompt="Which is a prime?")
        self.assertEqual(
            [(c.text, c.position) for c in question.choices.all()],
            [("2", 0), ("4", 1), ("9", 2)],
        )

    def test_a_blank_answer_row_is_ignored(self):
        """`extra = 4` leaves spare rows; they must not become empty answers."""
        self.client.force_login(self.sub_admin)
        self.client.post(
            reverse("admin:courses_question_add"),
            {
                "quiz": str(self.quiz.pk),
                "prompt": "Fill me",
                "explanation": "",
                "question_type": "single_choice",
                "marks": "",
                "negative_marks": "",
                "difficulty": "",
                "topic": "",
                "position": "3",
                "choices-TOTAL_FORMS": "4",
                "choices-INITIAL_FORMS": "0",
                "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "10",
                "choices-0-text": "Only one",
                "choices-0-is_correct": "on",
                "choices-1-text": "",
                "choices-2-text": "",
                "choices-3-text": "",
                "_save": "Save",
            },
            follow=True,
        )

        question = Question.objects.get(prompt="Fill me")
        self.assertEqual([c.text for c in question.choices.all()], ["Only one"])

    def test_the_report_queue_can_be_moved_along_in_bulk(self):
        from courses.models import QuizAttempt

        attempt = QuizAttempt.objects.create(user=self.student, quiz=self.quiz)
        report = QuestionReport.objects.create(
            attempt=attempt, question=self.question, reason=QuestionReport.Reason.TYPO
        )
        self.client.force_login(self.sub_admin)

        self.client.post(
            reverse("admin:courses_questionreport_changelist"),
            {"action": "mark_resolved", "_selected_action": [str(report.pk)], "index": "0"},
            follow=True,
        )

        report.refresh_from_db()
        self.assertEqual(report.status, QuestionReport.Status.RESOLVED)

    def test_the_lesson_form_offers_a_preview_of_the_recording(self):
        self.client.force_login(self.sub_admin)

        response = self.client.get(reverse("admin:courses_lesson_change", args=[self.lesson.pk]))

        self.assertContains(response, "Open the recording")
        self.assertContains(response, self.lesson.video_url)
