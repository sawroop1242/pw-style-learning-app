"""Cross-tenant writes are refused — audit finding 1, the P0 release blocker.

The platform is multi-provider: a sub-admin owns their batches and everything
inside them, and must never be able to reach into another provider's batch.
A queryset filter is not enough on a write, because a client can submit *any*
primary key in the body: the parent is chosen by the request, not by the URL.

These tests POST and PATCH foreign parents at every staff endpoint that has a
writable one, and assert that

* the write is refused with 403 and nothing is created or moved;
* the same write against the caller's own parent still succeeds;
* a main admin may do it, because that is what "main admin" means;
* a sub-admin can still read and edit their own question and choice, which the
  object permission used to deny while the list showed them.

Each test names the defect it pins, so a regression fails with the rule rather
than with a number.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import (
    AccessCode,
    Choice,
    Course,
    CourseFaculty,
    CourseFolder,
    Lesson,
    PdfResource,
    Question,
    Quiz,
    TestSeries,
)
from courses.models.access import generate_access_code, hash_access_code

User = get_user_model()


class TenantData(TestCase):
    """Two independent providers, each with a full set of content."""

    @classmethod
    def setUpTestData(cls):
        def make_user(name, role, staff=True):
            user = User.objects.create_user(
                username=name,
                email=f"{name}@example.com",
                password="TestPass123!",
                is_staff=staff,
            )
            user.profile.role = role
            user.profile.save()
            return user

        cls.main_admin = make_user("main", Role.MAIN_ADMIN)
        cls.alice = make_user("alice", Role.SUB_ADMIN)
        cls.bob = make_user("bob", Role.SUB_ADMIN)

        def provider_course(owner, slug, title):
            return Course.objects.create(
                title=title,
                slug=slug,
                owner=owner,
                pricing_mode=Course.PricingMode.PAID,
                price=Decimal("999.00"),
                is_published=True,
            )

        cls.alice_course = provider_course(cls.alice, "alice-batch", "Alice Batch")
        cls.bob_course = provider_course(cls.bob, "bob-batch", "Bob Batch")
        cls.bob_free = Course.objects.create(
            title="Bob Free", slug="bob-free", owner=cls.bob,
            pricing_mode=Course.PricingMode.FREE, is_published=True,
        )
        cls.alice_free = Course.objects.create(
            title="Alice Free", slug="alice-free", owner=cls.alice,
            pricing_mode=Course.PricingMode.FREE, is_published=True,
        )

        cls.alice_folder = CourseFolder.objects.create(course=cls.alice_course, title="Alice Week 1")
        cls.bob_folder = CourseFolder.objects.create(course=cls.bob_course, title="Bob Week 1")

        cls.alice_lesson = Lesson.objects.create(
            course=cls.alice_course, folder=cls.alice_folder, title="Alice Lesson"
        )
        cls.bob_lesson = Lesson.objects.create(
            course=cls.bob_course, folder=cls.bob_folder, title="Bob Lesson"
        )

        cls.alice_pdf = PdfResource.objects.create(
            folder=cls.alice_folder, title="Alice Notes", file_url="https://example.com/a.pdf"
        )
        cls.bob_pdf = PdfResource.objects.create(
            folder=cls.bob_folder, title="Bob Notes", file_url="https://example.com/b.pdf"
        )

        cls.alice_series = TestSeries.objects.create(
            title="Alice Series", slug="alice-series", owner=cls.alice
        )
        cls.bob_series = TestSeries.objects.create(
            title="Bob Series", slug="bob-series", owner=cls.bob
        )
        cls.bob_quiz = Quiz.objects.create(series=cls.bob_series, title="Bob Paper")
        cls.alice_quiz = Quiz.objects.create(course=cls.alice_course, title="Alice Paper")
        cls.bob_question = Question.objects.create(quiz=cls.bob_quiz, prompt="Bob Q1")
        cls.alice_question = Question.objects.create(quiz=cls.alice_quiz, prompt="Alice Q1")
        cls.bob_choice = Choice.objects.create(question=cls.bob_question, text="Bob A", is_correct=True)
        cls.alice_choice = Choice.objects.create(
            question=cls.alice_question, text="Alice A", is_correct=True
        )

        cls.alice_faculty = CourseFaculty.objects.create(course=cls.alice_course, name="Dr A")
        cls.bob_faculty = CourseFaculty.objects.create(course=cls.bob_course, name="Dr B")

        raw = generate_access_code()
        cls.alice_code = AccessCode.objects.create(
            course=cls.alice_course,
            code_hash=hash_access_code(raw),
            max_uses=5,
            created_by=cls.alice,
        )

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client


class FolderTenantTests(TenantData):
    def test_a_folder_cannot_be_created_in_another_providers_course(self):
        response = self.as_user(self.alice).post(
            "/api/staff/folders/", {"course": self.bob_course.id, "title": "Sneaky"}, format="json"
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(CourseFolder.objects.filter(title="Sneaky").exists())

    def test_a_folder_cannot_be_moved_into_another_providers_course(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/folders/{self.alice_folder.id}/",
            {"course": self.bob_course.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.alice_folder.refresh_from_db()
        self.assertEqual(self.alice_folder.course_id, self.alice_course.id)

    def test_the_owner_can_rename_their_own_folder(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/folders/{self.alice_folder.id}/", {"title": "Week One"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.alice_folder.refresh_from_db()
        self.assertEqual(self.alice_folder.title, "Week One")

    def test_a_main_admin_may_place_a_folder_in_any_course(self):
        response = self.as_user(self.main_admin).post(
            "/api/staff/folders/", {"course": self.alice_course.id, "title": "By Admin"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)


class LessonTenantTests(TenantData):
    def test_a_lesson_cannot_be_moved_to_another_providers_course(self):
        """The serializer refuses the half-empty pair, the view refuses the move.

        Either refusal is correct as long as nothing moves: changing the course
        alone leaves the section in the old batch, which the serializer rejects
        first. The next test submits a *consistent* pair, which only the
        ownership check can catch.
        """
        response = self.as_user(self.alice).patch(
            f"/api/staff/lessons/{self.alice_lesson.id}/",
            {"course": self.bob_course.id},
            format="json",
        )
        self.assertIn(response.status_code, {400, 403}, response.content)
        self.alice_lesson.refresh_from_db()
        self.assertEqual(self.alice_lesson.course_id, self.alice_course.id)

    def test_a_lesson_cannot_be_moved_to_another_providers_batch_and_section(self):
        """Course *and* section from the other provider: consistent, but foreign."""
        response = self.as_user(self.alice).patch(
            f"/api/staff/lessons/{self.alice_lesson.id}/",
            {"course": self.bob_course.id, "folder": self.bob_folder.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.alice_lesson.refresh_from_db()
        self.assertEqual(self.alice_lesson.course_id, self.alice_course.id)
        self.assertEqual(self.alice_lesson.folder_id, self.alice_folder.id)

    def test_a_lesson_cannot_be_moved_to_another_providers_folder(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/lessons/{self.alice_lesson.id}/",
            {"folder": self.bob_folder.id},
            format="json",
        )
        self.assertIn(response.status_code, {400, 403}, response.content)
        self.alice_lesson.refresh_from_db()
        self.assertEqual(self.alice_lesson.folder_id, self.alice_folder.id)

    def test_the_owner_can_still_edit_their_own_lesson(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/lessons/{self.alice_lesson.id}/", {"title": "Renamed"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)


class PdfTenantTests(TenantData):
    def test_a_pdf_cannot_be_created_in_another_providers_folder(self):
        response = self.as_user(self.alice).post(
            "/api/staff/pdfs/",
            {"folder": self.bob_folder.id, "title": "Sneaky", "file_url": "https://example.com/x.pdf"},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(PdfResource.objects.filter(title="Sneaky").exists())

    def test_a_pdf_cannot_be_moved_to_another_providers_folder(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/pdfs/{self.alice_pdf.id}/", {"folder": self.bob_folder.id}, format="json"
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.alice_pdf.refresh_from_db()
        self.assertEqual(self.alice_pdf.folder_id, self.alice_folder.id)


class AccessCodeTenantTests(TenantData):
    def test_a_code_cannot_be_created_for_another_providers_course(self):
        response = self.as_user(self.alice).post(
            "/api/staff/access-codes/", {"course": self.bob_course.id, "max_uses": 1}, format="json"
        )
        self.assertEqual(response.status_code, 403, response.content)

    def test_a_code_cannot_be_moved_to_another_providers_course(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/access-codes/{self.alice_code.id}/",
            {"course": self.bob_course.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.alice_code.refresh_from_db()
        self.assertEqual(self.alice_code.course_id, self.alice_course.id)

    def test_a_code_cannot_be_moved_onto_a_free_course(self):
        """The paid-only rule applies to an update, and before the write.

        Raising after `save()` would have left the code on a free batch while
        the request reported a 400.
        """
        response = self.as_user(self.alice).patch(
            f"/api/staff/access-codes/{self.alice_code.id}/",
            {"course": self.alice_free.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.alice_code.refresh_from_db()
        self.assertEqual(self.alice_code.course_id, self.alice_course.id)

    def test_another_provider_cannot_edit_my_code(self):
        response = self.as_user(self.bob).patch(
            f"/api/staff/access-codes/{self.alice_code.id}/",
            {"max_uses": 9},
            format="json",
        )
        self.assertIn(response.status_code, {403, 404}, response.content)
        self.alice_code.refresh_from_db()
        self.assertEqual(self.alice_code.max_uses, 5)


class QuizTenantTests(TenantData):
    def test_a_quiz_cannot_be_created_on_another_providers_course(self):
        response = self.as_user(self.alice).post(
            "/api/staff/quizzes/", {"course": self.bob_course.id, "title": "Sneaky"}, format="json"
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Quiz.objects.filter(title="Sneaky").exists())

    def test_a_quiz_cannot_be_created_in_another_providers_series(self):
        response = self.as_user(self.alice).post(
            "/api/staff/quizzes/", {"series": self.bob_series.id, "title": "Sneaky"}, format="json"
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Quiz.objects.filter(title="Sneaky").exists())

    def test_a_quiz_cannot_be_reparented_to_another_providers_course(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/quizzes/{self.alice_quiz.id}/",
            {"course": self.bob_course.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.alice_quiz.refresh_from_db()
        self.assertEqual(self.alice_quiz.course_id, self.alice_course.id)

    def test_a_quiz_cannot_be_reparented_to_another_providers_series(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/quizzes/{self.alice_quiz.id}/",
            {"series": self.bob_series.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)

    def test_the_owner_can_still_edit_their_own_quiz(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/quizzes/{self.alice_quiz.id}/", {"title": "Renamed"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)


class QuestionTenantTests(TenantData):
    def test_a_question_cannot_be_created_on_another_providers_quiz(self):
        response = self.as_user(self.alice).post(
            "/api/staff/questions/",
            {"quiz": self.bob_quiz.id, "prompt": "Sneaky"},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Question.objects.filter(prompt="Sneaky").exists())

    def test_a_question_cannot_be_moved_to_another_providers_quiz(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/questions/{self.alice_question.id}/",
            {"quiz": self.bob_quiz.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.alice_question.refresh_from_db()
        self.assertEqual(self.alice_question.quiz_id, self.alice_quiz.id)

    def test_a_sub_admin_can_read_their_own_question(self):
        """`IsOwnerOrMainAdmin` did not traverse quiz → course, so this 403'd."""
        response = self.as_user(self.alice).get(f"/api/staff/questions/{self.alice_question.id}/")
        self.assertEqual(response.status_code, 200, response.content)

    def test_a_sub_admin_cannot_read_another_providers_question(self):
        response = self.as_user(self.alice).get(f"/api/staff/questions/{self.bob_question.id}/")
        self.assertIn(response.status_code, {403, 404}, response.content)


class ChoiceTenantTests(TenantData):
    def test_a_choice_cannot_be_created_on_another_providers_question(self):
        response = self.as_user(self.alice).post(
            "/api/staff/choices/",
            {"question": self.bob_question.id, "text": "Sneaky"},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Choice.objects.filter(text="Sneaky").exists())

    def test_a_choice_cannot_be_moved_to_another_providers_question(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/choices/{self.alice_choice.id}/",
            {"question": self.bob_question.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.alice_choice.refresh_from_db()
        self.assertEqual(self.alice_choice.question_id, self.alice_question.id)

    def test_a_sub_admin_can_read_their_own_choice(self):
        response = self.as_user(self.alice).get(f"/api/staff/choices/{self.alice_choice.id}/")
        self.assertEqual(response.status_code, 200, response.content)


class FacultyTenantTests(TenantData):
    def test_faculty_cannot_be_moved_to_another_providers_course(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/faculty/{self.alice_faculty.id}/",
            {"course": self.bob_course.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.alice_faculty.refresh_from_db()
        self.assertEqual(self.alice_faculty.course_id, self.alice_course.id)

    def test_the_owner_can_still_edit_their_own_faculty(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/faculty/{self.alice_faculty.id}/", {"name": "Dr A."}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)


class CourseItselfTests(TenantData):
    def test_a_sub_admin_cannot_edit_another_providers_course(self):
        response = self.as_user(self.alice).patch(
            f"/api/staff/courses/{self.bob_course.id}/", {"title": "Taken over"}, format="json"
        )
        self.assertIn(response.status_code, {403, 404}, response.content)
        self.bob_course.refresh_from_db()
        self.assertEqual(self.bob_course.title, "Bob Batch")

    def test_a_sub_admin_cannot_publish_another_providers_course(self):
        self.bob_course.is_published = False
        self.bob_course.save(update_fields=["is_published"])
        response = self.as_user(self.alice).post(
            f"/api/staff/courses/{self.bob_course.id}/publish/"
        )
        self.assertIn(response.status_code, {403, 404}, response.content)
        self.bob_course.refresh_from_db()
        self.assertFalse(self.bob_course.is_published)


class SuperuserParityTests(TenantData):
    """A Django superuser is a main admin everywhere — audit finding 7.

    ``accounts.roles`` honoured ``is_superuser`` while ``courses.policy`` only
    read ``Profile.role``, so a superuser could pass the view permission and
    then be refused by the ownership check, or list only their own content.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.root = User.objects.create_superuser(
            username="root", email="root@example.com", password="TestPass123!"
        )

    def test_a_superuser_without_a_profile_role_is_a_main_admin(self):
        from courses.policy import is_main_admin, is_staff_role

        # The profile is auto-created as STUDENT, which is exactly the case
        # that used to disagree with accounts.roles.
        self.assertEqual(self.root.profile.role, Role.STUDENT)
        self.assertTrue(is_main_admin(self.root))
        self.assertTrue(is_staff_role(self.root))

    def test_a_superuser_lists_every_providers_content(self):
        response = self.as_user(self.root).get("/api/staff/courses/")
        self.assertEqual(response.status_code, 200, response.content)
        ids = {row["id"] for row in response.json()["results"]} if (
            isinstance(response.json(), dict) and "results" in response.json()
        ) else {row["id"] for row in response.json()}
        self.assertIn(self.alice_course.id, ids)
        self.assertIn(self.bob_course.id, ids)

    def test_a_superuser_can_write_into_a_sub_admins_content(self):
        response = self.as_user(self.root).post(
            "/api/staff/quizzes/",
            {"course": self.bob_course.id, "title": "Board paper"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_a_sub_admin_is_still_not_a_main_admin(self):
        from courses.policy import is_main_admin

        self.assertFalse(is_main_admin(self.alice))
