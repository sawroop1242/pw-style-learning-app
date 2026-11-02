"""The upload pipeline: validation, naming, the HEAD proof, and delivery.

The bucket is a fake, not Cloudflare: ``r2.put_object`` and ``r2.object_head``
are patched so the tests can assert *what was sent* and *what a lying bucket
does* without an account. The rule the tests defend is the one that matters —
an upload the bucket did not keep is never reported as success.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import AuditEvent, Role
from courses.models import Course, CourseFolder, PdfResource
from objectstore import r2, services, uploads
from objectstore.models import Purpose, R2Account, R2Bucket

User = get_user_model()

ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def make_user(name, role=Role.SUB_ADMIN):
    user = User.objects.create_user(
        username=name, email=f"{name}@example.com", password="TestPass123!", is_staff=True
    )
    user.profile.role = role
    user.profile.save()
    return user


class ValidationTests(TestCase):
    def test_a_pdf_is_accepted_and_normalised(self):
        self.assertEqual(
            uploads.validate_upload("pdfs", "Chapter 1.PDF", "application/pdf; charset=binary", 10),
            "application/pdf",
        )

    def test_the_extension_must_agree_with_the_declared_type(self):
        # A browser will happily hand over .html labelled as an image, and the
        # bucket would serve it back as that type.
        with self.assertRaises(uploads.UploadRefused) as caught:
            uploads.validate_upload("course_images", "payload.html", "image/png", 10)
        self.assertIn(".html", str(caught.exception))

    def test_a_disallowed_type_says_what_is_allowed(self):
        with self.assertRaises(uploads.UploadRefused) as caught:
            uploads.validate_upload("pdfs", "notes.docx", "application/msword", 10)
        self.assertIn("application/pdf", str(caught.exception))

    def test_the_size_ceiling_is_per_purpose(self):
        with self.assertRaises(uploads.UploadRefused) as caught:
            uploads.validate_upload("pdfs", "big.pdf", "application/pdf", 65 * 1024 * 1024)
        self.assertIn("64 MiB", str(caught.exception))

    def test_an_empty_file_is_refused_before_it_reaches_the_bucket(self):
        for size in (0, -1):
            with self.assertRaises(uploads.UploadRefused):
                uploads.validate_upload("pdfs", "empty.pdf", "application/pdf", size)

    def test_an_unknown_purpose_lists_the_real_ones(self):
        with self.assertRaises(uploads.UploadRefused) as caught:
            uploads.validate_upload("videos", "clip.mp4", "video/mp4", 10)
        self.assertIn("pdfs", str(caught.exception))
        self.assertIn("course_images", str(caught.exception))

    def test_video_is_not_a_storable_purpose(self):
        # Lessons play from an embed URL; no bucket takes half-gigabyte files.
        self.assertNotIn("videos", uploads.PURPOSE_RULES)

    def test_the_key_hides_the_original_name_and_is_unique(self):
        owner = make_user("keys")
        first = uploads.object_key(owner, "pdfs", "student-name-chapter-1.pdf")
        second = uploads.object_key(owner, "pdfs", "student-name-chapter-1.pdf")

        self.assertRegex(first, rf"^{owner.pk}/pdfs/[0-9a-f]{{32}}\.pdf$")
        self.assertNotIn("student", first)
        self.assertNotEqual(first, second)


@override_settings(R2_SIGNED_URL_TTL=900)
class StoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("provider")
        cls.account = R2Account.objects.create(
            owner=cls.owner, name="Cloudflare", account_id=ACCOUNT_ID
        )
        cls.account.set_credentials(ACCESS_KEY, SECRET_KEY)
        cls.account.save()

    def setUp(self):
        self.bucket = R2Bucket.objects.create(
            account=self.account, name="notes", allow_pdfs=True, is_default_pdfs=True
        )

    def test_a_kept_upload_returns_a_signed_url_and_an_audit_row(self):
        with mock.patch.object(r2, "put_object") as put, mock.patch.object(
            r2, "object_head", return_value=200
        ):
            stored = uploads.store(
                self.owner, self.owner, "pdfs",
                filename="chapter.pdf", content_type="application/pdf", data=PDF,
            )

        put.assert_called_once()
        args, kwargs = put.call_args
        self.assertEqual(args[1], "notes")
        self.assertEqual(args[2], stored.key)
        self.assertEqual(kwargs["content_type"], "application/pdf")
        self.assertTrue(stored.url.startswith("https://"))
        self.assertIsNotNone(stored.expires_at)
        self.assertEqual(stored.size, len(PDF))

        event = AuditEvent.objects.get(action="asset_upload")
        self.assertEqual(event.outcome, "success")
        self.assertIn("pdfs", str(event.metadata))
        self.assertNotIn("chapter", str(event.metadata))

    def test_a_put_without_the_object_is_a_failure_not_a_success(self):
        # A bucket can answer 200 to PUT and still not have the object (wrong
        # key, a lifecycle rule, a read-only token). HEAD is the proof.
        with mock.patch.object(r2, "put_object"), mock.patch.object(
            r2, "object_head", return_value=404
        ):
            with self.assertRaises(uploads.UploadRefused) as caught:
                uploads.store(
                    self.owner, self.owner, "pdfs",
                    filename="chapter.pdf", content_type="application/pdf", data=PDF,
                )

        self.assertIn("404", str(caught.exception))
        self.assertEqual(
            AuditEvent.objects.get(action="asset_upload").outcome, "failed"
        )
        self.assertFalse(PdfResource.objects.exists())

    def test_a_network_error_is_reported_without_a_traceback(self):
        with mock.patch.object(r2, "put_object", side_effect=r2.R2Error("connection reset")):
            with self.assertRaises(uploads.UploadRefused) as caught:
                uploads.store(
                    self.owner, self.owner, "pdfs",
                    filename="chapter.pdf", content_type="application/pdf", data=PDF,
                )
        self.assertIn("connection reset", str(caught.exception))

    def test_no_bucket_for_the_purpose_is_explained_not_raised_as_500(self):
        # Untick the purpose *and* the default: a bucket marked default for a
        # purpose is re-enabled for it on save (see R2Bucket.save).
        self.bucket.allow_pdfs = False
        self.bucket.is_default_pdfs = False
        self.bucket.save()

        with self.assertRaises(uploads.UploadRefused) as caught:
            uploads.store(
                self.owner, self.owner, "pdfs",
                filename="chapter.pdf", content_type="application/pdf", data=PDF,
            )
        self.assertIn("No R2 bucket", str(caught.exception))

    def test_a_public_bucket_gives_a_permanent_url(self):
        self.bucket.public_base_url = "https://files.example.com"
        self.bucket.save()

        with mock.patch.object(r2, "put_object"), mock.patch.object(
            r2, "object_head", return_value=200
        ):
            stored = uploads.store(
                self.owner, self.owner, "pdfs",
                filename="chapter.pdf", content_type="application/pdf", data=PDF,
            )

        self.assertIsNone(stored.expires_at)
        self.assertEqual(stored.url, f"https://files.example.com/{stored.key}")

    def test_an_upload_writes_to_the_owners_bucket_not_the_actors(self):
        main = make_user("main-admin", role=Role.MAIN_ADMIN)
        with mock.patch.object(r2, "put_object") as put, mock.patch.object(
            r2, "object_head", return_value=200
        ):
            stored = uploads.store(
                main, self.owner, "pdfs",
                filename="chapter.pdf", content_type="application/pdf", data=PDF,
            )

        self.assertEqual(put.call_args[0][1], "notes")
        self.assertTrue(stored.key.startswith(f"{self.owner.pk}/"))
        self.assertEqual(
            AuditEvent.objects.get(action="asset_upload").actor, main
        )


@override_settings(R2_SIGNED_URL_TTL=900)
class UrlForKeyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("reader-owner")
        cls.account = R2Account.objects.create(
            owner=cls.owner, name="Cloudflare", account_id=ACCOUNT_ID
        )
        cls.account.set_credentials(ACCESS_KEY, SECRET_KEY)
        cls.account.save()

    def test_no_key_means_no_url(self):
        self.assertIsNone(uploads.url_for_key(self.owner, "pdfs", ""))

    def test_no_storage_configured_returns_none_instead_of_raising(self):
        self.assertIsNone(uploads.url_for_key(self.owner, "pdfs", "1/pdfs/abc.pdf"))

    def test_a_configured_bucket_signs_the_key(self):
        R2Bucket.objects.create(account=self.account, name="notes", allow_pdfs=True)
        url = uploads.url_for_key(self.owner, "pdfs", "1/pdfs/abc.pdf")
        self.assertIn("1/pdfs/abc.pdf", url)
        self.assertIn("X-Amz-Signature", url)


@override_settings(R2_SIGNED_URL_TTL=900)
class UploadEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("endpoint-provider")
        cls.other = make_user("endpoint-rival")
        cls.account = R2Account.objects.create(
            owner=cls.owner, name="Cloudflare", account_id=ACCOUNT_ID
        )
        cls.account.set_credentials(ACCESS_KEY, SECRET_KEY)
        cls.account.save()
        cls.course = Course.objects.create(
            owner=cls.owner, title="Batch", slug="batch-upload", subject="Physics"
        )

    def setUp(self):
        R2Bucket.objects.create(account=self.account, name="notes", allow_pdfs=True)
        self.url = reverse("staff-upload")

    def post(self, user, **data):
        client = APIClient()
        client.force_authenticate(user)
        payload = {"purpose": "pdfs", "course": self.course.pk}
        payload.update(data)
        return client.post(self.url, payload, format="multipart")

    def test_a_pdf_is_stored_and_the_key_is_returned(self):
        with mock.patch.object(r2, "put_object"), mock.patch.object(
            r2, "object_head", return_value=200
        ):
            response = self.post(
                self.owner,
                file=SimpleUploadedFile("chapter.pdf", PDF, content_type="application/pdf"),
            )

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["purpose"], "pdfs")
        self.assertTrue(body["key"].endswith(".pdf"))
        self.assertNotIn("chapter", body["key"])

    def test_another_provider_cannot_upload_into_someone_elses_batch(self):
        response = self.post(
            self.other,
            file=SimpleUploadedFile("chapter.pdf", PDF, content_type="application/pdf"),
        )
        self.assertEqual(response.status_code, 403)

    def test_an_anonymous_upload_is_refused(self):
        response = APIClient().post(
            self.url,
            {"purpose": "pdfs", "course": self.course.pk,
             "file": SimpleUploadedFile("chapter.pdf", PDF, content_type="application/pdf")},
            format="multipart",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_a_bad_purpose_is_a_400_that_names_the_good_ones(self):
        response = self.post(
            self.owner,
            purpose="videos",
            file=SimpleUploadedFile("clip.mp4", b"\x00" * 16, content_type="video/mp4"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("pdfs", response.json()["purpose"][0])

    def test_a_missing_file_is_a_400_not_a_crash(self):
        response = self.post(self.owner)
        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.json())

    def test_a_missing_course_is_a_400(self):
        response = self.post(
            self.owner,
            course="",
            file=SimpleUploadedFile("chapter.pdf", PDF, content_type="application/pdf"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.json())

    def test_an_unknown_course_is_a_400(self):
        response = self.post(
            self.owner,
            course="999999",
            file=SimpleUploadedFile("chapter.pdf", PDF, content_type="application/pdf"),
        )
        self.assertEqual(response.status_code, 400)

    def test_a_refused_file_returns_the_reason(self):
        response = self.post(
            self.owner,
            file=SimpleUploadedFile("notes.docx", b"x", content_type="application/msword"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("application/pdf", response.json()["file"][0])


@override_settings(R2_SIGNED_URL_TTL=900)
class KeyBackedDeliveryTests(TestCase):
    """A row that holds a key serves a fresh URL; a row that holds a link is gone."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("delivery-provider")
        cls.learner = User.objects.create_user(
            username="delivery-learner", password="TestPass123!"
        )
        cls.account = R2Account.objects.create(
            owner=cls.owner, name="Cloudflare", account_id=ACCOUNT_ID
        )
        cls.account.set_credentials(ACCESS_KEY, SECRET_KEY)
        cls.account.save()
        cls.course = Course.objects.create(
            owner=cls.owner, title="Batch", slug="batch-delivery", subject="Physics",
            is_published=True,
        )
        cls.folder = CourseFolder.objects.create(
            course=cls.course, title="Notes", position=0
        )

    def setUp(self):
        R2Bucket.objects.create(account=self.account, name="notes", allow_pdfs=True)
        self.client = APIClient()

    def test_a_stored_pdf_is_served_as_a_signed_url(self):
        resource = PdfResource.objects.create(
            folder=self.folder, title="Chapter", file_key="1/pdfs/abc.pdf",
            is_published=True, is_protected=False,
        )
        self.client.force_authenticate(self.learner)
        response = self.client.get(reverse("pdf-detail", args=[resource.pk]))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("1/pdfs/abc.pdf", body["file_url"])
        self.assertIn("X-Amz-Signature", body["file_url"])

    def test_a_stored_pdf_stays_locked_for_a_non_learner(self):
        resource = PdfResource.objects.create(
            folder=self.folder, title="Chapter", file_key="1/pdfs/abc.pdf",
            is_published=True, is_protected=True,
        )
        self.client.force_authenticate(self.learner)
        body = self.client.get(reverse("pdf-detail", args=[resource.pk])).json()

        self.assertIsNone(body["file_url"])
        self.assertIsNone(body["viewer_url"])
        self.assertTrue(body["is_locked"])

    def test_storage_going_away_falls_back_to_the_pasted_link(self):
        resource = PdfResource.objects.create(
            folder=self.folder, title="Chapter", file_key="1/pdfs/abc.pdf",
            file_url="https://files.example.com/chapter.pdf",
            is_published=True, is_protected=False,
        )
        self.client.force_authenticate(self.learner)
        with mock.patch.object(services, "resolve_bucket", side_effect=services.NoStorageTarget("x")):
            body = self.client.get(reverse("pdf-detail", args=[resource.pk])).json()

        self.assertEqual(body["file_url"], "https://files.example.com/chapter.pdf")
        self.assertFalse(body["is_locked"])

    def test_the_staff_serializer_needs_a_file_or_a_link(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            reverse("staff-pdf-list"),
            {"folder": self.folder.pk, "title": "Chapter"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("file_url", response.json())

    def test_the_staff_serializer_accepts_a_key_alone(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            reverse("staff-pdf-list"),
            {"folder": self.folder.pk, "title": "Chapter", "file_key": "1/pdfs/abc.pdf"},
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            PdfResource.objects.get(pk=response.json()["id"]).file_key, "1/pdfs/abc.pdf"
        )
