from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile, Role
from courses.models import (
    AccessCode,
    AttemptAnswer,
    Bookmark,
    Choice,
    CommunityPost,
    Course,
    CourseAccessGrant,
    CourseFolder,
    CsvImportJob,
    Lesson,
    Note,
    PdfResource,
    Progress,
    Question,
    Quiz,
    QuizAttempt,
    RevisionItem,
    StudyTask,
    TestSeries,
)
from courses.models.access import generate_access_code, hash_access_code

User = get_user_model()


class TestDataMixin:
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
        cls.sub_admin_two = User.objects.create_user(
            username="subadmin2", email="sub2@example.com", password="TestPass123!", is_staff=True
        )
        cls.sub_admin_two.profile.role = Role.SUB_ADMIN
        cls.sub_admin_two.profile.save()
        cls.student = User.objects.create_user(
            username="student", email="student@example.com", password="TestPass123!"
        )
        cls.course = Course.objects.create(
            title="UPSC Basics",
            slug="upsc-basics",
            subject="General",
            owner=cls.sub_admin,
            pricing_mode=Course.PricingMode.FREE,
        )
        cls.paid_course = Course.objects.create(
            title="Paid Course",
            slug="paid-course",
            subject="General",
            owner=cls.sub_admin,
            pricing_mode=Course.PricingMode.PAID,
            price=Decimal("499.00"),
        )
        cls.other_course = Course.objects.create(
            title="Other Provider",
            slug="other-provider",
            subject="General",
            owner=cls.sub_admin_two,
            pricing_mode=Course.PricingMode.FREE,
        )
        cls.folder = CourseFolder.objects.create(course=cls.course, title="Folder One", position=1)
        cls.lesson = Lesson.objects.create(
            course=cls.course, folder=cls.folder, title="Lesson One", position=1, is_published=True
        )
        cls.pdf = PdfResource.objects.create(
            folder=cls.folder, title="Chapter PDF", file_url="https://example.com/chapter.pdf"
        )
        cls.series = TestSeries.objects.create(
            title="Mock Series", slug="mock-series", owner=cls.sub_admin, is_published=True
        )
        cls.quiz = Quiz.objects.create(
            series=cls.series, title="Mock Test 1", timing_mode=Quiz.TimingMode.TIMED, duration_minutes=60
        )
        cls.question = Question.objects.create(quiz=cls.quiz, prompt="What is 2+2?")
        cls.correct = Choice.objects.create(question=cls.question, text="4", is_correct=True)
        cls.wrong = Choice.objects.create(question=cls.question, text="5", is_correct=False)


class ProfileSignalTests(TestCase):
    def test_profile_created_with_student_role(self):
        user = User.objects.create_user("newuser", "new@example.com", "TestPass123!")
        self.assertEqual(user.profile.role, Role.STUDENT)

    def test_profile_role_helpers(self):
        user = User.objects.create_user("ruser", "r@example.com", "TestPass123!")
        self.assertFalse(user.profile.is_main_admin)
        self.assertFalse(user.profile.is_staff_role)
        user.profile.role = Role.SUB_ADMIN
        user.profile.save()
        self.assertTrue(user.profile.is_sub_admin)
        self.assertTrue(user.profile.is_staff_role)


class CourseModelTests(TestDataMixin, TestCase):
    def test_slug_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Course.objects.create(
                    title="Duplicate", slug="upsc-basics", owner=self.sub_admin
                )

    def test_free_course_requires_zero_price(self):
        with self.assertRaises(ValidationError):
            Course(
                title="Bad Free", slug="bad-free", pricing_mode=Course.PricingMode.FREE, price=Decimal("10.00")
            ).clean()

    def test_paid_course_requires_positive_price(self):
        with self.assertRaises(ValidationError):
            Course(
                title="Bad Paid", slug="bad-paid", pricing_mode=Course.PricingMode.PAID, price=Decimal("0.00")
            ).clean()

    def test_paid_course_with_price_is_valid(self):
        Course(
            title="Good Paid", slug="good-paid", pricing_mode=Course.PricingMode.PAID, price=Decimal("1.00")
        ).clean()

    def test_telegram_handle_validation(self):
        with self.assertRaises(ValidationError):
            Course(title="T", slug="t-tel", telegram_handle="provider").clean()

    def test_courses_default_to_draft(self):
        self.assertFalse(Course(title="D", slug="draft-default").is_published)
        self.assertFalse(Lesson(course=self.course, title="L").is_published)


class FolderLessonPdfTests(TestDataMixin, TestCase):
    def test_folder_title_unique_per_course(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CourseFolder.objects.create(course=self.course, title="Folder One")

    def test_lesson_folder_must_match_course(self):
        lesson = Lesson(course=self.course, folder=CourseFolder.objects.create(course=self.other_course, title="X", position=1))
        with self.assertRaises(ValidationError):
            lesson.clean()

    def test_lesson_ordering(self):
        second = Lesson.objects.create(course=self.course, title="Lesson Two", position=0)
        lessons = list(Lesson.objects.filter(course=self.course))
        self.assertEqual(lessons[0], second)

    def test_pdf_course_property(self):
        self.assertEqual(self.pdf.course, self.course)


class AccessCodeTests(TestDataMixin, TestCase):
    def test_code_generation_entropy(self):
        codes = {generate_access_code() for _ in range(50)}
        self.assertEqual(len(codes), 50)

    def test_hash_is_not_plaintext_and_is_deterministic(self):
        raw = generate_access_code()
        hashed = hash_access_code(raw)
        self.assertNotEqual(hashed, raw)
        self.assertNotIn(raw, hashed)
        self.assertEqual(hashed, hash_access_code(raw))
        self.assertNotEqual(hashed, hash_access_code("different-code"))

    def test_code_hash_unique(self):
        raw = generate_access_code()
        AccessCode.objects.create(course=self.paid_course, code_hash=hash_access_code(raw))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccessCode.objects.create(course=self.paid_course, code_hash=hash_access_code(raw))

    def test_status_transitions(self):
        code = AccessCode.objects.create(course=self.paid_course, code_hash=hash_access_code(generate_access_code()))
        self.assertEqual(code.status, AccessCode.Status.UNUSED)
        code.uses_count = 1
        self.assertEqual(code.status, AccessCode.Status.REDEEMED)
        code.uses_count = 0
        code.revoked_at = timezone.now()
        self.assertEqual(code.status, AccessCode.Status.REVOKED)

    def test_expiry(self):
        code = AccessCode(
            course=self.paid_course,
            code_hash=hash_access_code(generate_access_code()),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertTrue(code.is_expired)

    def test_default_single_use(self):
        code = AccessCode(course=self.paid_course, code_hash=hash_access_code(generate_access_code()))
        self.assertEqual(code.max_uses, 1)


class GrantTests(TestDataMixin, TestCase):
    def test_grant_unique_per_user_course(self):
        CourseAccessGrant.objects.create(user=self.student, course=self.paid_course)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CourseAccessGrant.objects.create(user=self.student, course=self.paid_course)

    def test_grant_active_property(self):
        grant = CourseAccessGrant.objects.create(user=self.student, course=self.paid_course)
        self.assertTrue(grant.is_active)
        grant.revoked_at = timezone.now()
        self.assertFalse(grant.is_active)

    def test_code_revocation_does_not_revoke_grant(self):
        """Documented policy: only explicit grant revocation removes access."""
        code = AccessCode.objects.create(course=self.paid_course, code_hash=hash_access_code(generate_access_code()))
        grant = CourseAccessGrant.objects.create(user=self.student, course=self.paid_course, access_code=code)
        code.revoked_at = timezone.now()
        code.save()
        grant.refresh_from_db()
        self.assertTrue(grant.is_active)


class QuizEngineModelTests(TestDataMixin, TestCase):
    def test_timed_quiz_requires_duration(self):
        with self.assertRaises(ValidationError):
            Quiz(title="No Duration", timing_mode=Quiz.TimingMode.TIMED).clean()

    def test_quiz_owner_resolution(self):
        self.assertEqual(self.quiz.owner, self.sub_admin)
        course_quiz = Quiz.objects.create(course=self.course, title="Course Quiz")
        self.assertEqual(course_quiz.owner, self.sub_admin)
        self.assertIsNone(Quiz(title="Orphan").owner)

    def test_attempt_default_ordering_and_flags(self):
        attempt = QuizAttempt.objects.create(user=self.student, quiz=self.quiz)
        self.assertEqual(attempt.status, QuizAttempt.Status.IN_PROGRESS)
        self.assertFalse(attempt.is_released)
        self.assertEqual(QuizAttempt.objects.count(), 1)

    def test_attempt_answer_unique_per_question(self):
        attempt = QuizAttempt.objects.create(user=self.student, quiz=self.quiz, question_order=[self.question.id])
        AttemptAnswer.objects.create(attempt=attempt, question=self.question)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AttemptAnswer.objects.create(attempt=attempt, question=self.question)

    def test_csv_import_job_metadata_only(self):
        job = CsvImportJob.objects.create(
            quiz=self.quiz, source_url="https://example.com/questions.csv", requested_by=self.sub_admin
        )
        field_names = {f.name for f in CsvImportJob._meta.fields}
        self.assertNotIn("file", field_names)
        self.assertNotIn("raw_content", field_names)
        self.assertEqual(job.status, CsvImportJob.Status.PENDING)

    def test_series_owner_scoped(self):
        owned = TestSeries.objects.filter(owner=self.sub_admin)
        self.assertIn(self.series, owned)
        self.assertNotIn(
            TestSeries.objects.create(title="Other", slug="other-series", owner=self.sub_admin_two), owned
        )


class PersonalDataModelTests(TestDataMixin, TestCase):
    def test_note_optional_links(self):
        note = Note.objects.create(user=self.student, lesson=self.lesson, title="Note", body="Content")
        self.assertEqual(note.lesson, self.lesson)
        self.assertIsNone(note.question)

    def test_progress_unique_user_lesson(self):
        Progress.objects.create(user=self.student, lesson=self.lesson, completed=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Progress.objects.create(user=self.student, lesson=self.lesson)

    def test_bookmark_unique_per_resource(self):
        Bookmark.objects.create(user=self.student, resource=self.lesson)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Bookmark.objects.create(user=self.student, resource=self.lesson)
        Bookmark.objects.create(user=self.student, resource=self.course)

    def test_bookmark_rejects_unbookmarkable_type(self):
        post = CommunityPost.objects.create(title="Post", body="Body", author=self.sub_admin)
        with self.assertRaises(ValidationError):
            Bookmark(user=self.student, resource=post).clean()

    def test_revision_item_unique_and_types(self):
        RevisionItem.objects.create(user=self.student, resource=self.lesson)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RevisionItem.objects.create(user=self.student, resource=self.lesson)
        with self.assertRaises(ValidationError):
            RevisionItem(user=self.student, resource=self.course).clean()

    def test_study_task_defaults_and_validation(self):
        task = StudyTask(user=self.student, title="Revise algebra")
        task.clean()
        task.save()
        self.assertEqual(task.priority, StudyTask.Priority.MEDIUM)
        self.assertFalse(task.is_completed)
        with self.assertRaises(ValidationError):
            StudyTask(user=self.student, title="Bad", duration_minutes=0).clean()


class CommunityPostModelTests(TestDataMixin, TestCase):
    def test_pinned_posts_sort_first(self):
        plain = CommunityPost.objects.create(title="Plain", body="b", author=self.sub_admin)
        pinned = CommunityPost.objects.create(
            title="Pinned", body="b", author=self.main_admin, is_pinned=True
        )
        posts = list(CommunityPost.objects.all())
        self.assertEqual(posts[0], pinned)
        self.assertIn(plain, posts)

    def test_default_draft(self):
        post = CommunityPost(title="Draft", body="b", author=self.main_admin)
        self.assertFalse(post.is_published)
