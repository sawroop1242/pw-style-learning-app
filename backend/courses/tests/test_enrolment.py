"""Enrolment, the "added today" feed, and PDF viewer URLs.

Three behaviours are pinned here, because each one replaced something the app
used to do automatically:

* a free batch is joined with a button press, not handed out by the catalogue;
* the home page's latest classes are today's uploads in the batches a learner
  actually joined;
* a PDF link is turned into a frameable viewer URL, with the provider's own
  embed link winning when an editor supplies one.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import Role
from courses.models import (
    Course,
    CourseAccessGrant,
    CourseFolder,
    Lesson,
    PdfResource,
)
from courses.models.catalog import viewer_url_for

User = get_user_model()

PDFHOST = (
    "https://pdfhost.io/v/gW5zHHvLvw_Practice_Test-02_Yakeen_NEET_Hindi_2_0"
    "__2026__17_08_2025_Questions"
)


class EnrolmentData(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="TestPass123!"
        )
        cls.admin.profile.role = Role.MAIN_ADMIN
        cls.admin.profile.save()

        cls.student = User.objects.create_user(
            username="student", email="student@example.com", password="TestPass123!"
        )
        cls.student.profile.role = Role.STUDENT
        cls.student.profile.save()

        cls.free = Course.objects.create(
            title="Free Batch",
            slug="free-batch",
            owner=cls.admin,
            pricing_mode=Course.PricingMode.FREE,
            is_published=True,
        )
        cls.folder = CourseFolder.objects.create(course=cls.free, title="Week 1")
        cls.lesson = Lesson.objects.create(
            course=cls.free,
            folder=cls.folder,
            title="Recording",
            video_url="https://embed.vcdn.me/embed/28c4af9f-d817-460a-80ab-9a09f8c47c69",
            is_published=True,
        )

        cls.paid = Course.objects.create(
            title="Paid Batch",
            slug="paid-batch",
            owner=cls.admin,
            pricing_mode=Course.PricingMode.PAID,
            price=499,
            is_published=True,
        )
        cls.hidden = Course.objects.create(
            title="Draft Batch",
            slug="draft-batch",
            owner=cls.admin,
            pricing_mode=Course.PricingMode.FREE,
            is_published=False,
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient(raise_request_exception=False)

    def as_student(self):
        self.client.force_authenticate(self.student)
        return self.client

    def enrol(self, course=None):
        return self.client.post(f"/api/courses/{(course or self.free).id}/enroll/")


class EnrolEndpointTests(EnrolmentData):
    def test_a_guest_cannot_enrol(self):
        response = self.enrol()
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(CourseAccessGrant.objects.filter(course=self.free).exists())

    def test_the_first_enrolment_creates_the_grant(self):
        self.as_student()
        response = self.enrol()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["is_enrolled"])
        self.assertTrue(response.json()["created"])
        grant = CourseAccessGrant.objects.get(user=self.student, course=self.free)
        self.assertIsNone(grant.revoked_at)
        self.assertEqual(grant.granted_by, self.student)

    def test_enrolling_twice_is_not_an_error_and_does_not_duplicate(self):
        self.as_student()
        self.enrol()
        second = self.enrol()

        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])
        self.assertEqual(
            CourseAccessGrant.objects.filter(user=self.student, course=self.free).count(), 1
        )

    def test_enrolling_again_restores_a_revoked_grant(self):
        grant = CourseAccessGrant.objects.create(
            user=self.student, course=self.free, granted_by=self.admin
        )
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])

        self.assertFalse(
            CourseAccessGrant.objects.filter(
                user=self.student, course=self.free, revoked_at__isnull=True
            ).exists()
        )

        self.as_student()
        response = self.enrol()

        self.assertEqual(response.status_code, 201)
        grant.refresh_from_db()
        self.assertIsNone(grant.revoked_at)
        self.assertNotEqual(grant.granted_by, self.student)

    def test_a_paid_batch_asks_for_an_access_code_instead(self):
        self.as_student()
        response = self.enrol(self.paid)

        self.assertEqual(response.status_code, 400)
        self.assertIn("access code", response.json()["detail"].lower())
        self.assertFalse(
            CourseAccessGrant.objects.filter(user=self.student, course=self.paid).exists()
        )

    def test_an_unpublished_batch_is_404(self):
        self.as_student()
        self.assertEqual(self.enrol(self.hidden).status_code, 404)

    def test_enrolling_unlocks_the_batch_media(self):
        self.as_student()
        before = self.client.get(f"/api/courses/{self.free.id}/").json()
        self.assertFalse(before["is_enrolled"])
        self.assertNotIn("embed.vcdn.me", str(before))

        self.enrol()

        after = self.client.get(f"/api/courses/{self.free.id}/").json()
        self.assertTrue(after["has_access"])
        self.assertTrue(after["is_enrolled"])
        self.assertIn("embed.vcdn.me", str(after))

        lessons = self.client.get("/api/lessons/").json()["results"]
        self.assertEqual([row["title"] for row in lessons], ["Recording"])

    def test_the_enrolment_shows_up_in_my_batches_only_after_the_tap(self):
        self.as_student()
        self.assertEqual(self.client.get("/api/courses/?mine=1").json()["results"], [])

        self.enrol()

        rows = self.client.get("/api/courses/?mine=1").json()["results"]
        self.assertEqual([row["slug"] for row in rows], ["free-batch"])


class TodaysClassesTests(EnrolmentData):
    def setUp(self):
        super().setUp()
        old = timezone.now() - timedelta(days=3)
        Lesson.objects.filter(pk=self.lesson.pk).update(created_at=old)
        # Today's upload in the joined batch, and one in a batch nobody joined.
        self.fresh = Lesson.objects.create(
            course=self.free,
            folder=self.folder,
            title="Today's class",
            video_url="https://embed.vcdn.me/embed/28c4af9f-d817-460a-80ab-9a09f8c47c69",
            is_published=True,
        )
        other = Course.objects.create(
            title="Other Free Batch",
            slug="other-free",
            owner=self.admin,
            pricing_mode=Course.PricingMode.FREE,
            is_published=True,
        )
        other_folder = CourseFolder.objects.create(course=other, title="Week 1")
        self.elsewhere = Lesson.objects.create(
            course=other,
            folder=other_folder,
            title="Not my class",
            video_url="https://embed.vcdn.me/embed/28c4af9f-d817-460a-80ab-9a09f8c47c69",
            is_published=True,
        )
        self.silent = Lesson.objects.create(
            course=self.free, folder=self.folder, title="Notes only", is_published=True
        )

    def feed(self):
        return self.client.get("/api/lessons/?added=today&has_video=1")

    def test_the_feed_is_empty_until_the_learner_enrols(self):
        self.assertEqual(self.feed().json()["results"], [])

    def test_the_feed_is_todays_video_classes_in_joined_batches(self):
        self.as_student()
        self.enrol()

        titles = [row["title"] for row in self.feed().json()["results"]]

        self.assertEqual(titles, ["Today's class"])

    def test_yesterdays_class_is_not_on_todays_feed(self):
        self.as_student()
        self.enrol()

        titles = [row["title"] for row in self.feed().json()["results"]]

        self.assertNotIn("Recording", titles)
        self.assertNotIn("Not my class", titles)
        self.assertNotIn("Notes only", titles)


class ViewerUrlTests(TestCase):
    def test_an_editor_supplied_embed_url_wins(self):
        self.assertEqual(
            viewer_url_for("https://example.com/a.pdf", "https://example.com/embed/1"),
            "https://example.com/embed/1",
        )

    def test_a_direct_pdf_is_framed_as_is(self):
        url = "https://files.example.com/notes/chapter-1.pdf"
        self.assertEqual(viewer_url_for(url), url)

    def test_a_google_drive_view_link_becomes_its_preview(self):
        self.assertEqual(
            viewer_url_for("https://drive.google.com/file/d/abc123/view?usp=sharing"),
            "https://drive.google.com/file/d/abc123/preview?usp=sharing",
        )

    def test_a_pdfhost_share_page_is_framed_as_its_own_reader(self):
        """The link the owner gave us is already a reader, so it is not wrapped.

        pdfhost's /v/<id> page is its PDF viewer; /embed/<id> answers 404 and
        the page serves no file URL of its own. Framing it as it stands shows
        the document; putting Google's viewer in front of it showed Google's
        rendering of the share page instead of the PDF.
        """
        self.assertEqual(viewer_url_for(PDFHOST), PDFHOST)

    def test_a_blank_resource_has_no_viewer(self):
        self.assertEqual(viewer_url_for(""), "")


class PdfViewerApiTests(EnrolmentData):
    def setUp(self):
        super().setUp()
        self.pdf = PdfResource.objects.create(
            folder=self.folder,
            title="Practice test",
            file_url=PDFHOST,
            is_published=True,
            is_protected=True,
        )
        self.nearby = PdfResource.objects.create(
            folder=self.folder,
            title="Formula sheet",
            file_url="https://files.example.com/formula.pdf",
            is_published=True,
            is_protected=True,
        )

    def test_the_list_returns_a_viewer_url_for_a_joined_learner(self):
        self.as_student()
        self.enrol()

        rows = {row["title"]: row for row in self.client.get("/api/pdfs/").json()["results"]}

        self.assertEqual(rows["Practice test"]["viewer_url"], PDFHOST)
        self.assertEqual(
            rows["Formula sheet"]["viewer_url"], "https://files.example.com/formula.pdf"
        )
        self.assertFalse(rows["Practice test"]["is_locked"])
        self.assertEqual(rows["Practice test"]["course"], self.free.id)
        self.assertEqual(rows["Practice test"]["course_slug"], "free-batch")

    def test_the_viewer_url_is_withheld_from_a_non_enrolled_visitor(self):
        rows = {row["title"]: row for row in self.client.get("/api/pdfs/").json()["results"]}

        self.assertTrue(rows["Practice test"]["is_locked"])
        self.assertIsNone(rows["Practice test"]["viewer_url"])
        self.assertIsNone(rows["Practice test"]["file_url"])

    def test_an_explicit_embed_url_is_what_the_reader_frames(self):
        self.pdf.embed_url = "https://pdfhost.io/embed/abc"
        self.pdf.save(update_fields=["embed_url"])
        self.as_student()
        self.enrol()

        row = self.client.get(f"/api/pdfs/{self.pdf.id}/").json()

        self.assertEqual(row["embed_url"], "https://pdfhost.io/embed/abc")
        self.assertEqual(row["viewer_url"], "https://pdfhost.io/embed/abc")
