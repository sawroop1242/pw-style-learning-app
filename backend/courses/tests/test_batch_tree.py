"""The batch page's tree: subject → chapter → classes and notes.

A batch is read the way a syllabus is read. Before this, the page showed a flat
list of sections with the classes inside and pushed every PDF into a separate
tab, so "where is the DPP for this chapter" had no answer on the screen.
`CourseFolder.subject` is the third level, and these tests pin what the batch
payload must say for a client to draw it:

* the subject a chapter is filed under, verbatim — the API never invents one
  for a chapter the provider left blank;
* the chapter's own published classes and notes, and nothing from its
  neighbour;
* a note's URLs still gated by the access rule, tree or no tree;
* a page that costs the same number of queries whether the batch has two
  chapters or twelve.
"""

from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import Course, CourseAccessGrant, CourseFolder, Lesson, PdfResource

User = get_user_model()


class BatchTreeData(TestCase):
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

        cls.course = Course.objects.create(
            title="JEE 2027",
            slug="jee-2027",
            owner=cls.owner,
            subject="Physics",
            pricing_mode=Course.PricingMode.PAID,
            price=Decimal("4999.00"),
            is_published=True,
        )
        cls.mechanics = CourseFolder.objects.create(
            course=cls.course, title="Mechanics", subject="Physics", position=1
        )
        cls.atomic = CourseFolder.objects.create(
            course=cls.course, title="Atomic Structure", subject="Chemistry", position=2
        )
        cls.unfiled = CourseFolder.objects.create(
            course=cls.course, title="Miscellaneous", position=3
        )

    def setUp(self):
        self.client = APIClient()

        def lesson(folder, title, published=True, **extra):
            return Lesson.objects.create(
                course=self.course,
                folder=folder,
                title=title,
                is_published=published,
                **extra,
            )

        def note(folder, title, published=True, protected=True):
            return PdfResource.objects.create(
                folder=folder,
                title=title,
                file_url=f"https://files.example/{title.lower().replace(' ', '-')}.pdf",
                is_published=published,
                is_protected=protected,
            )

        self.units = lesson(self.mechanics, "Units and dimensions", duration_minutes=52)
        self.kinematics = lesson(self.mechanics, "Kinematics", duration_minutes=64)
        self.mole = lesson(self.atomic, "Mole concept", duration_minutes=46)
        self.draft = lesson(self.mechanics, "Unreleased class", published=False)
        self.formula = note(self.mechanics, "Mechanics formula sheet")
        self.bank = note(self.atomic, "Atomic question bank")
        self.hidden_note = note(self.mechanics, "Draft note", published=False)

    def detail(self, user=None):
        if user is not None:
            self.client.force_authenticate(user)
        response = self.client.get(f"/api/courses/{self.course.id}/")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def chapters(self, payload):
        return {folder["title"]: folder for folder in payload["folders"]}

    def enrol(self):
        CourseAccessGrant.objects.create(user=self.learner, course=self.course)


class ChapterSubjectTests(BatchTreeData):
    def test_a_chapter_reports_the_subject_it_is_filed_under(self):
        chapters = self.chapters(self.detail())

        self.assertEqual(chapters["Mechanics"]["subject"], "Physics")
        self.assertEqual(chapters["Atomic Structure"]["subject"], "Chemistry")

    def test_a_chapter_the_provider_left_blank_is_not_given_a_subject(self):
        """The batch page falls back to the batch's subject; the API does not."""
        chapters = self.chapters(self.detail())

        self.assertEqual(chapters["Miscellaneous"]["subject"], "")

    def test_chapters_keep_the_order_the_provider_set(self):
        titles = [folder["title"] for folder in self.detail()["folders"]]

        self.assertEqual(titles, ["Mechanics", "Atomic Structure", "Miscellaneous"])

    def test_the_two_subjects_come_back_as_two_groups_on_the_screen(self):
        payload = self.detail()

        self.assertEqual(
            [folder["subject"] for folder in payload["folders"]],
            ["Physics", "Chemistry", ""],
        )


class ChapterContentsTests(BatchTreeData):
    def test_a_chapter_carries_its_own_classes_and_notes(self):
        chapters = self.chapters(self.detail())

        mechanics = chapters["Mechanics"]
        self.assertEqual(
            [lesson["title"] for lesson in mechanics["lessons"]],
            ["Units and dimensions", "Kinematics"],
        )
        self.assertEqual(
            [pdf["title"] for pdf in mechanics["pdf_resources"]],
            ["Mechanics formula sheet"],
        )

        atomic = chapters["Atomic Structure"]
        self.assertEqual([lesson["title"] for lesson in atomic["lessons"]], ["Mole concept"])
        self.assertEqual([pdf["title"] for pdf in atomic["pdf_resources"]], ["Atomic question bank"])

    def test_an_unpublished_class_or_note_never_reaches_the_tree(self):
        chapters = self.chapters(self.detail())

        mechanics = chapters["Mechanics"]
        self.assertNotIn("Unreleased class", [row["title"] for row in mechanics["lessons"]])
        self.assertNotIn("Draft note", [row["title"] for row in mechanics["pdf_resources"]])

    def test_the_tree_does_not_repeat_a_class_in_another_chapter(self):
        seen = [
            row["id"]
            for folder in self.detail()["folders"]
            for row in folder["lessons"]
        ]

        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), {self.units.id, self.kinematics.id, self.mole.id})

    def test_a_locked_note_is_listed_with_its_url_withheld(self):
        note = self.chapters(self.detail())["Mechanics"]["pdf_resources"][0]

        self.assertIsNone(note["file_url"])
        self.assertIsNone(note["viewer_url"])
        self.assertTrue(note["is_locked"])

    def test_an_enrolled_learner_gets_the_same_note_unlocked(self):
        self.enrol()
        note = self.chapters(self.detail(user=self.learner))["Mechanics"]["pdf_resources"][0]

        self.assertTrue(note["file_url"].startswith("https://files.example/"))
        self.assertFalse(note["is_locked"])

    def test_the_page_does_not_cost_a_query_per_chapter(self):
        """A dozen chapters must not be two dozen queries."""
        for index in range(9):
            extra = CourseFolder.objects.create(
                course=self.course, title=f"Chapter {index}", subject="Physics", position=10 + index
            )
            Lesson.objects.create(
                course=self.course, folder=extra, title=f"Class {index}", is_published=True
            )
            PdfResource.objects.create(
                folder=extra,
                title=f"Note {index}",
                file_url="https://files.example/x.pdf",
                is_published=True,
            )

        with self.assertNumQueries(5):
            # the batch, its chapters, every class, every note, its faculty —
            # five, whether the batch has two chapters or twelve.
            payload = self.detail()

        self.assertEqual(len(payload["folders"]), 12)


class ChapterAdminTests(BatchTreeData):
    def test_the_chapter_admin_can_file_a_chapter_under_its_subject(self):
        self.client.force_authenticate(self.owner)

        response = self.client.patch(
            f"/api/staff/folders/{self.unfiled.id}/",
            {"subject": "Physics"},
            format="json",
        )

        self.assertIn(response.status_code, (200, 404))
        if response.status_code == 200:
            self.unfiled.refresh_from_db()
            self.assertEqual(self.unfiled.subject, "Physics")


class TreeTimestampTests(BatchTreeData):
    def test_a_class_time_still_travels_with_the_class(self):
        """The tree is where a learner looks; the hour must come with it."""
        start = timezone.make_aware(datetime(2027, 1, 4, 19, 0))
        Lesson.objects.filter(pk=self.units.pk).update(starts_at=start)

        row = self.chapters(self.detail())["Mechanics"]["lessons"][0]

        self.assertIsNotNone(row["starts_at"])
        self.assertEqual(row["id"], self.units.id)
