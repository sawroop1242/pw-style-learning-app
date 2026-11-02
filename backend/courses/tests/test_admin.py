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

    def test_a_superuser_without_a_profile_role_can_open_a_changelist(self):
        """`createsuperuser` sets no Profile role, and that must not lock it out.

        The console decided access from Profile.role alone, so an account made
        with Django's own command could sign in and then be refused every model
        page with a 403 — no message, no clue.
        """
        boss = User.objects.create_user(
            "boss", "boss@example.com", "TestPass123!", is_superuser=True, is_staff=True
        )
        self.client.force_login(boss)

        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(self.client.get("/admin/courses/quiz/").status_code, 200)

    def test_a_student_is_still_refused_a_changelist(self):
        self.client.force_login(self.student)

        self.assertIn(self.client.get("/admin/courses/quiz/").status_code, (302, 403))

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
        self.assertEqual(self.client.get(url).status_code, 200)

        # The batch picker is an autocomplete, so its options are not in the
        # page — they come from the admin's autocomplete view. That view reads
        # the model admin's own queryset, so it is where the scoping now has to
        # hold: it must never offer a batch this sub-admin does not own.
        search = self.client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "courses",
                "model_name": "accesscode",
                "field_name": "course",
                "term": "",
            },
        )
        self.assertEqual(search.status_code, 200)
        labels = [row["text"] for row in search.json()["results"]]
        self.assertIn(self.own_course.title, labels)
        self.assertNotIn(self.other_course.title, labels)

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

    def test_the_lesson_form_lists_sections_from_every_batch(self):
        """One list, every section, and each option names its batch.

        Nothing is filtered by the selected batch or by ownership: the whole
        catalogue is in the dropdown, labelled “Batch — Section” so two
        sections called “Week 1” can be told apart.
        """
        foreign_folder = CourseFolder.objects.create(
            course=self.other_course, title="Optics", position=1
        )
        self.client.force_login(self.sub_admin)

        response = self.client.get(reverse("admin:courses_lesson_change", args=[self.lesson.pk]))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(f'<option value="{foreign_folder.pk}">', body)
        self.assertIn(f"{self.other_course.title} — Optics", body)
        # A real, selectable option — not a disabled label.
        self.assertNotIn("disabled", body.split(f'value="{foreign_folder.pk}"')[1][:120])
        self.assertIn(f"{self.own_course.title} — ", body)
        # No browser-side filtering is needed any more.
        self.assertNotIn("staff/lesson_folder.js", body)

    def test_picking_another_batchs_section_moves_the_lesson_to_that_batch(self):
        foreign_folder = CourseFolder.objects.create(
            course=self.other_course, title="Optics", position=1
        )
        self.client.force_login(self.main_admin)

        response = self.client.post(
            reverse("admin:courses_lesson_add"),
            {
                "title": "Lenses",
                "course": self.own_course.pk,  # deliberately the wrong batch
                "folder": foreign_folder.pk,
                "duration_minutes": 30,
                "position": 1,
                "is_published": "0",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        lesson = Lesson.objects.get(title="Lenses")
        self.assertEqual(lesson.course, self.other_course)
        self.assertEqual(lesson.folder, foreign_folder)

    def test_a_sub_admin_cannot_file_a_lesson_into_another_teachers_section(self):
        """Seeing every section must not mean writing into every section."""
        foreign_folder = CourseFolder.objects.create(
            course=self.other_course, title="Optics", position=1
        )
        self.client.force_login(self.sub_admin)

        response = self.client.post(
            reverse("admin:courses_lesson_add"),
            {
                "title": "Borrowed",
                "folder": foreign_folder.pk,
                "duration_minutes": 30,
                "position": 1,
                "is_published": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Lesson.objects.filter(title="Borrowed").exists())
        self.assertContains(response, "belongs to another teacher")

    def test_a_batch_page_shows_its_cover_image_field(self):
        self.client.force_login(self.sub_admin)

        response = self.client.get(reverse("admin:courses_course_change", args=[self.own_course.pk]))

        self.assertContains(response, "Artwork")
        self.assertContains(response, 'name="image_url"')

    def test_the_lesson_form_offers_a_preview_of_the_recording(self):
        self.client.force_login(self.sub_admin)

        response = self.client.get(reverse("admin:courses_lesson_change", args=[self.lesson.pk]))

        self.assertContains(response, "Open the recording")
        self.assertContains(response, self.lesson.video_url)


class AdminStructureTests(AdminTestDataMixin, TestCase):
    """The parent pages own their children.

    The complaint behind this was structural, not visual: building a batch meant
    hopping between six flat model lists and re-picking the parent from a
    dropdown each time. These tests hold the new arrangement in place — a
    section page holds its own classes and PDFs, and the "add" links carry the
    parent id so nothing has to be picked twice.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.folder = CourseFolder.objects.create(
            course=cls.own_course, title="Mechanics", position=1
        )
        cls.lesson = Lesson.objects.create(
            course=cls.own_course,
            folder=cls.folder,
            title="Units",
            video_url="https://embed.vcdn.me/embed/28c4af9f-d817-460a-80ab-9a09f8c47c69",
            duration_minutes=52,
            position=1,
        )

    def test_a_section_page_holds_its_own_classes_and_notes(self):
        self.client.force_login(self.sub_admin)

        response = self.client.get(reverse("admin:courses_coursefolder_change", args=[self.folder.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Classes in this section")
        self.assertContains(response, "Notes and PDFs")
        # The existing class is editable there, not just linked to.
        self.assertContains(response, "Units")

    def test_a_batch_page_holds_its_own_sections(self):
        self.client.force_login(self.sub_admin)

        response = self.client.get(reverse("admin:courses_course_change", args=[self.own_course.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sections (folders of classes)")
        self.assertContains(response, "Mechanics")

    def test_a_class_added_inside_a_section_lands_in_the_sections_batch(self):
        """The section knows its batch; the inline must not ask for it again."""
        self.client.force_login(self.sub_admin)

        response = self.client.post(
            reverse("admin:courses_coursefolder_change", args=[self.folder.pk]),
            {
                "course": self.own_course.pk,
                "title": "Mechanics",
                "description": "",
                "position": 1,
                "lessons-TOTAL_FORMS": 1,
                "lessons-INITIAL_FORMS": 1,
                "lessons-MIN_NUM_FORMS": 0,
                "lessons-MAX_NUM_FORMS": 1000,
                "lessons-0-id": self.lesson.pk,
                "lessons-0-title": "Units",
                "lessons-0-video_url": self.lesson.video_url,
                "lessons-0-duration_minutes": 52,
                "lessons-0-position": 1,
                "lessons-0-is_published": "on",
                "pdfs-TOTAL_FORMS": 0,
                "pdfs-INITIAL_FORMS": 0,
                "pdfs-MIN_NUM_FORMS": 0,
                "pdfs-MAX_NUM_FORMS": 1000,
                "_continue": "Save and continue editing",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.course_id, self.own_course.pk)
        self.assertEqual(self.lesson.title, "Units")

    def test_the_add_links_carry_the_parent_id(self):
        self.client.force_login(self.sub_admin)

        response = self.client.get(reverse("admin:courses_course_change", args=[self.own_course.pk]))

        # "+ Add a class" lands on a form whose batch is already chosen.
        self.assertContains(
            response,
            f"{reverse('admin:courses_lesson_add')}?course={self.own_course.pk}",
            html=False,
        )
        self.assertContains(response, f"{reverse('admin:courses_coursefolder_add')}?course={self.own_course.pk}")

        folder_page = self.client.get(reverse("admin:courses_coursefolder_change", args=[self.folder.pk]))
        self.assertContains(folder_page, f"{reverse('admin:courses_lesson_add')}?folder={self.folder.pk}")

    def test_the_lesson_form_arrives_with_the_batch_prefilled(self):
        self.client.force_login(self.sub_admin)

        response = self.client.get(reverse("admin:courses_lesson_add"), {"course": self.own_course.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["adminform"].form["course"].value(), self.own_course.pk)

        from_folder = self.client.get(reverse("admin:courses_lesson_add"), {"folder": self.folder.pk})

        form = from_folder.context["adminform"].form
        self.assertEqual(form["course"].value(), self.own_course.pk)
        self.assertEqual(form["folder"].value(), self.folder.pk)

    def test_the_navigation_rail_is_grouped_by_job(self):
        """The rail is grouped the same way the console home is.

        Both read `WORKFLOWS` in courses/templatetags/admin_nav.py, so a model
        is in the same place in the rail as on the home cards. Checked on a
        model list rather than the home, because the rail is on every page.
        """
        self.client.force_login(self.main_admin)

        response = self.client.get(reverse("admin:courses_lesson_changelist"))

        self.assertEqual(response.status_code, 200)
        for title in (
            "Batches and lessons",
            "Tests and questions",
            "Access and enrolment",
            "Announcements and reports",
            "Learner activity",
            "People and permissions",
        ):
            self.assertContains(response, title)

        # The rail is still the shape nav_sidebar.js filters on — one row per
        # model with the link inside a `th[scope=row]`. Filtering hides rows;
        # a group with nothing left is hidden by the script.
        rows = response.content.count(b'<th scope="row">')
        self.assertGreater(rows, 20)
        self.assertIn(b'<th scope="row">', response.content)
        self.assertContains(response, '<a href="/admin/courses/course/">Courses</a>', html=False)

        # A sub-admin only sees the groups they can act on, so the rail is
        # scoped by permission like everything else.
        self.client.force_login(self.sub_admin)
        scoped = self.client.get(reverse("admin:courses_lesson_changelist"))
        self.assertContains(scoped, "Batches and lessons")
        self.assertNotContains(scoped, "People and permissions")

    def test_every_publishable_list_page_opens_and_offers_publish(self):
        """Bulk publish is declared once, in PublishableAdmin.

        `@admin.action` only marks a method — it has to be named in `actions`
        to be registered. Missing that made the Course and Quiz list pages
        raise KeyError and 500, which no test caught because every other test
        logged in as a sub-admin who could not open them.
        """
        from courses.admin import PublishableAdmin

        self.client.force_login(self.main_admin)
        request = self.request_for(self.main_admin)

        checked = 0
        for model, model_admin in admin.site._registry.items():
            if not isinstance(model_admin, PublishableAdmin):
                continue
            with self.subTest(model=model.__name__):
                response = self.client.get(
                    reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
                )
                # Rendering the list is the part that used to 500.
                self.assertEqual(response.status_code, 200)
                # The action is registered, so it can be picked in the dropdown
                # (an empty list page renders no dropdown at all).
                self.assertIn("publish_selected", model_admin.get_actions(request))
                checked += 1

        self.assertEqual(checked, 3)


class AdminPresentationTests(AdminTestDataMixin, TestCase):
    """Small things a person reads on every screen.

    None of these are permission rules, so none of the earlier tests noticed
    them: a list titled "Select quiz to change", a 26-character timestamp per
    row, a ten-row textarea around a two-line blurb.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.quiz = Quiz.objects.create(
            title="Mock 1", series=None, course=cls.own_course, duration_minutes=60,
            timing_mode="timed", is_published=True,
        )

    def test_a_list_is_titled_after_what_it_holds(self):
        """Including the lists Django owns, which our ModelAdmins never see."""
        self.client.force_login(self.main_admin)

        for url_name, heading in (
            ("admin:courses_quiz_changelist", "<h1>Quizzes</h1>"),
            ("admin:courses_course_changelist", "<h1>Courses</h1>"),
            ("admin:courses_question_changelist", "<h1>Questions</h1>"),
            ("admin:auth_user_changelist", "<h1>Users</h1>"),
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, heading, html=False)
                # "Select quiz to change" is the phrase being retired. (Django's
                # select-all checkbox label legitimately starts with "Select".)
                self.assertNotIn(b" to change", response.content)

    def test_the_updated_column_is_a_short_stamp(self):
        from courses.admin import QuizAdmin

        model_admin = QuizAdmin(Quiz, admin.site)
        stamp = model_admin.last_edited(self.quiz)

        # Django's own rendering of updated_at is "Nov. 1, 2026, 8:41 p.m.",
        # which is the widest cell in the list.
        self.assertLessEqual(len(stamp), 14)
        self.assertNotIn(",", stamp)

    def test_long_text_fields_ask_for_four_lines(self):
        self.client.force_login(self.main_admin)

        response = self.client.get(reverse("admin:courses_course_change", args=[self.own_course.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rows="4"')
        self.assertNotContains(response, 'rows="10"')

    def test_a_new_batch_starts_out_owned_by_whoever_is_signed_in(self):
        # Sub-admins never see the owner field; for them save_model assigns it.
        self.client.force_login(self.main_admin)

        response = self.client.get(reverse("admin:courses_course_add"))

        self.assertEqual(response.status_code, 200)
        # The owner picker is pre-selected, so a batch cannot be saved with no
        # owner by simply not touching that field.
        self.assertContains(response, f'<option value="{self.main_admin.pk}" selected>')
