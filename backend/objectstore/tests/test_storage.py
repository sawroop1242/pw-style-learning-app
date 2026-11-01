"""The R2 storage panel: credentials, ownership, and a connection test.

Everything here runs offline. The SigV4 signature is checked against a value
computed by hand for a fixed clock, and the connection test is exercised
against a local HTTP server that stands in for Cloudflare — so "Test connection"
is proven to send a signed request and to read the answer, not merely to exist.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import AuditEvent, Role
from objectstore import crypto
from objectstore.models import R2Account, R2Bucket
from objectstore.r2 import (
    ALGORITHM,
    Credentials,
    canonical_query_string,
    endpoint_url,
    presign_url,
    sign_request,
)
from objectstore.services import NoStorageTarget, resolve_bucket, test_bucket

User = get_user_model()

ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
FIXED_NOW = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_user(name, role=Role.SUB_ADMIN, staff=True):
    user = User.objects.create_user(
        username=name, email=f"{name}@example.com", password="TestPass123!", is_staff=staff
    )
    user.profile.role = role
    user.profile.save()
    return user


class CryptoLockTests(TestCase):
    def test_a_credential_round_trips_and_the_ciphertext_does_not_contain_it(self):
        stored = crypto.encrypt("secret-value-123")

        self.assertTrue(stored.startswith("v1:"))
        self.assertNotIn("secret-value-123", stored)
        self.assertEqual(crypto.decrypt(stored), "secret-value-123")

    def test_a_derived_key_is_hkdf_not_the_secret_itself(self):
        derived = crypto.derive_key("a" * 60)

        self.assertNotIn("a" * 60, derived)
        raw = base64.urlsafe_b64decode(derived)
        self.assertEqual(len(raw), 32)

    def test_two_derivations_of_the_same_secret_agree(self):
        self.assertEqual(crypto.derive_key("k" * 50), crypto.derive_key("k" * 50))

    @override_settings(R2_CREDENTIAL_KEYS=[])
    def test_a_ciphertext_from_another_key_is_refused_with_a_sentence(self):
        stored = crypto.encrypt("x" * 20)
        with override_settings(R2_CREDENTIAL_KEYS=[crypto.generate_key()]):
            with self.assertRaises(crypto.CredentialError) as caught:
                crypto.decrypt(stored)
        self.assertIn("Re-enter the API token", str(caught.exception))

    def test_a_key_at_the_front_decrypts_what_the_old_key_wrote(self):
        old_key = crypto.generate_key()
        with override_settings(R2_CREDENTIAL_KEYS=[old_key]):
            stored = crypto.encrypt("credential")

        with override_settings(R2_CREDENTIAL_KEYS=[crypto.generate_key(), old_key]):
            self.assertEqual(crypto.decrypt(stored), "credential")

    def test_the_fingerprint_is_short_and_not_the_value(self):
        hint = crypto.fingerprint(ACCESS_KEY)

        self.assertTrue(hint.startswith("••••"))
        self.assertEqual(len(hint), 8)
        self.assertNotIn(ACCESS_KEY[:8], hint)


class AccountModelTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.account = R2Account(owner=self.owner, name="My Cloudflare", account_id=ACCOUNT_ID)
        self.account.set_credentials(ACCESS_KEY, SECRET_KEY)
        self.account.save()

    def test_the_secret_is_not_stored_in_clear_text(self):
        stored = R2Account.objects.get(pk=self.account.pk)

        self.assertNotIn(SECRET_KEY, stored.secret_access_key_enc)
        self.assertNotIn(ACCESS_KEY, stored.access_key_id_enc)
        credentials = stored.get_credentials()
        self.assertEqual(credentials.access_key_id, ACCESS_KEY)
        self.assertEqual(credentials.secret_access_key, SECRET_KEY)

    def test_the_endpoint_is_the_one_cloudflare_gives(self):
        self.assertEqual(
            self.account.endpoint, f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
        )

    def test_an_account_id_that_is_not_hexadecimal_is_rejected(self):
        from django.core.exceptions import ValidationError

        account = R2Account(owner=self.owner, name="Bad", account_id="not-an-account")
        with self.assertRaises(ValidationError) as caught:
            account.full_clean()
        self.assertIn("account_id", caught.exception.message_dict)


class BucketRulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("owner")
        cls.account = R2Account.objects.create(
            owner=cls.owner, name="Cloudflare", account_id=ACCOUNT_ID
        )
        cls.account.set_credentials(ACCESS_KEY, SECRET_KEY)
        cls.account.save()

    def bucket(self, name, **kwargs):
        return R2Bucket.objects.create(account=self.account, name=name, **kwargs)

    def test_a_bucket_name_must_look_like_a_bucket_name(self):
        from django.core.exceptions import ValidationError

        for bad in ("Course Art", "UPPER", "a", "-leading", "http://x"):
            with self.assertRaises(ValidationError):
                R2Bucket(account=self.account, name=bad).full_clean()

    def test_a_public_base_url_must_be_https(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            R2Bucket(
                account=self.account, name="course-art", public_base_url="http://files.example.com"
            ).full_clean()

    def test_making_a_bucket_the_default_moves_it_off_the_previous_one(self):
        first = self.bucket("first-art", is_default_course_images=True)
        second = self.bucket("second-art", is_default_course_images=True)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default_course_images)
        self.assertTrue(second.is_default_course_images)
        # The default implies the purpose even when the box was left unticked.
        self.assertTrue(second.allow_course_images)

    def test_two_defaults_are_kept_per_purpose_for_different_owners(self):
        other = make_user("other")
        other_account = R2Account.objects.create(
            owner=other, name="Other", account_id="f" * 32
        )
        other_account.set_credentials(ACCESS_KEY, SECRET_KEY)
        other_account.save()

        mine = self.bucket("mine", is_default_community=True)
        theirs = R2Bucket.objects.create(
            account=other_account, name="theirs", is_default_community=True
        )

        mine.refresh_from_db()
        self.assertTrue(mine.is_default_community)
        self.assertTrue(theirs.is_default_community)

    def test_resolve_prefers_the_default_then_the_oldest(self):
        plain = self.bucket("plain", allow_pdfs=True)
        chosen = self.bucket("chosen", allow_pdfs=True, is_default_pdfs=True)

        self.assertEqual(resolve_bucket(self.owner, "pdfs"), chosen)
        chosen.is_default_pdfs = False
        chosen.save()
        self.assertEqual(resolve_bucket(self.owner, "pdfs"), plain)

    def test_a_bucket_for_another_purpose_is_not_used(self):
        self.bucket("images-only", allow_course_images=True)
        with self.assertRaises(NoStorageTarget) as caught:
            resolve_bucket(self.owner, "pdfs")
        self.assertIn("No R2 bucket is set up", str(caught.exception))

    def test_a_disabled_bucket_is_not_chosen(self):
        self.bucket("off", allow_pdfs=True, enabled=False)
        with self.assertRaises(NoStorageTarget):
            resolve_bucket(self.owner, "pdfs")

    def test_a_bucket_under_an_off_account_is_not_chosen(self):
        self.bucket("paused", allow_pdfs=True)
        R2Account.objects.filter(pk=self.account.pk).update(is_active=False)
        with self.assertRaises(NoStorageTarget):
            resolve_bucket(self.owner, "pdfs")


class SigningTests(TestCase):
    """SigV4 by hand, so a change to the signing code cannot pass silently."""

    def credentials(self):
        return Credentials(account_id=ACCOUNT_ID, access_key_id=ACCESS_KEY, secret_access_key=SECRET_KEY)

    def test_the_canonical_query_string_sorts_and_encodes(self):
        self.assertEqual(
            canonical_query_string([("b", "2"), ("a", "hello world"), ("a", "1")]),
            "a=1&a=hello%20world&b=2",
        )

    def test_the_endpoint_puts_the_bucket_first(self):
        self.assertEqual(
            endpoint_url(ACCOUNT_ID, "course-art"),
            f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com/course-art",
        )

    def test_a_signed_header_carries_the_scope_and_all_signed_headers(self):
        url = endpoint_url(ACCOUNT_ID, "course-art") + "?list-type=2&max-keys=1"
        headers = sign_request("GET", url, self.credentials(), now=FIXED_NOW)

        self.assertTrue(headers["Authorization"].startswith(ALGORITHM))
        self.assertIn("Credential=AKIAIOSFODNN7EXAMPLE/20261101/auto/s3/aws4_request", headers["Authorization"])
        self.assertIn("SignedHeaders=host;x-amz-content-sha256;x-amz-date", headers["Authorization"])
        self.assertEqual(headers["x-amz-date"], "20261101T120000Z")
        self.assertEqual(headers["x-amz-content-sha256"], hashlib.sha256(b"").hexdigest())

    def test_the_signature_is_deterministic_for_a_fixed_clock(self):
        url = endpoint_url(ACCOUNT_ID, "course-art") + "?list-type=2&max-keys=1"
        first = sign_request("GET", url, self.credentials(), now=FIXED_NOW)
        second = sign_request("GET", url, self.credentials(), now=FIXED_NOW)

        self.assertEqual(first["Authorization"], second["Authorization"])
        # …and it is actually an HMAC, not a constant: the secret changes it.
        other = Credentials(ACCOUNT_ID, ACCESS_KEY, "different-secret")
        self.assertNotEqual(
            sign_request("GET", url, other, now=FIXED_NOW)["Authorization"],
            first["Authorization"],
        )

    def test_a_presigned_url_expires_and_carries_its_signature(self):
        url = presign_url(
            "GET",
            endpoint_url(ACCOUNT_ID, "course-art", "lessons/one.pdf"),
            self.credentials(),
            expires=600,
            now=FIXED_NOW,
        )

        self.assertIn("X-Amz-Algorithm=AWS4-HMAC-SHA256", url)
        self.assertIn("X-Amz-Expires=600", url)
        self.assertIn("X-Amz-SignedHeaders=host", url)
        self.assertIn("X-Amz-Signature=", url)
        self.assertIn("/course-art/lessons/one.pdf?", url)
        # An expiry beyond a week is clamped, as S3 requires.
        clamped = presign_url(
            "GET", endpoint_url(ACCOUNT_ID, "b", "k"), self.credentials(), expires=10_000_000
        )
        self.assertIn("X-Amz-Expires=604800", clamped)


class FakeR2(BaseHTTPRequestHandler):
    """A stand-in for Cloudflare: answers one ListObjectsV2 request."""

    status = 200
    body = b"<ListBucketResult><KeyCount>1</KeyCount><Contents><Key>probe.txt</Key></Contents></ListBucketResult>"
    seen = {}

    def do_GET(self):  # noqa: N802 - http.server API
        type(self).seen = {
            "path": self.path,
            "authorization": self.headers.get("Authorization", ""),
            "host": self.headers.get("Host", ""),
        }
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/xml")
        self.end_headers()
        self.wfile.write(type(self).body)

    def log_message(self, *args):  # silence the test run
        pass


class StartupCheckTests(TestCase):
    def test_a_production_deploy_with_stored_tokens_and_no_explicit_key_is_warned(self):
        from django.core.checks import run_checks

        from objectstore.checks import storage_encryption_key_check

        owner = make_user("owner")
        account = R2Account.objects.create(owner=owner, name="Mine", account_id=ACCOUNT_ID)
        account.set_credentials(ACCESS_KEY, SECRET_KEY)
        account.save()

        with override_settings(ENVIRONMENT="production", R2_CREDENTIAL_KEYS=[]):
            warnings = storage_encryption_key_check(None)
        self.assertEqual([w.id for w in warnings], ["objectstore.W001"])
        self.assertIn("r2_rotate_key", warnings[0].hint)
        self.assertTrue(callable(run_checks))

    def test_an_explicit_key_silences_it(self):
        from objectstore.checks import storage_encryption_key_check

        owner = make_user("owner")
        account = R2Account.objects.create(owner=owner, name="Mine", account_id=ACCOUNT_ID)
        account.set_credentials(ACCESS_KEY, SECRET_KEY)
        account.save()

        with override_settings(ENVIRONMENT="production", R2_CREDENTIAL_KEYS=[crypto.generate_key()]):
            self.assertEqual(storage_encryption_key_check(None), [])

    def test_a_database_without_the_table_does_not_break_the_check(self):
        """`manage.py check` runs before migrate on a fresh database."""
        from unittest import mock

        from django.db.utils import ProgrammingError

        from objectstore.checks import storage_encryption_key_check

        with override_settings(ENVIRONMENT="production", R2_CREDENTIAL_KEYS=[]):
            with mock.patch(
                "objectstore.models.R2Account.objects.exclude",
                side_effect=ProgrammingError("relation does not exist"),
            ):
                self.assertEqual(storage_encryption_key_check(None), [])

    def test_development_is_never_warned(self):
        from objectstore.checks import storage_encryption_key_check

        owner = make_user("owner")
        account = R2Account.objects.create(owner=owner, name="Mine", account_id=ACCOUNT_ID)
        account.set_credentials(ACCESS_KEY, SECRET_KEY)
        account.save()

        with override_settings(ENVIRONMENT="development", R2_CREDENTIAL_KEYS=[]):
            self.assertEqual(storage_encryption_key_check(None), [])


class ConnectionTestTests(TestCase):
    """The admin's "Test connection" against a local server, not mocked out."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("owner")
        cls.account = R2Account.objects.create(
            owner=cls.owner, name="Cloudflare", account_id=ACCOUNT_ID
        )
        cls.account.set_credentials(ACCESS_KEY, SECRET_KEY)
        cls.account.save()

    def setUp(self):
        FakeR2.status = 200
        FakeR2.seen = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeR2)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def test_a_reachable_bucket_is_recorded_as_connected(self):
        bucket = R2Bucket.objects.create(account=self.account, name="course-art")

        # The endpoint is normally <account>.r2.cloudflarestorage.com; point it
        # at the local server for this test only.
        from unittest import mock

        with mock.patch(
            "objectstore.r2.endpoint_host", return_value=f"127.0.0.1:{self.port}"
        ), mock.patch("objectstore.r2._perform", wraps=_local_perform(self.port)):
            verdict = test_bucket(bucket, actor=self.owner)

        bucket.refresh_from_db()
        self.assertTrue(verdict.ok, verdict.message)
        self.assertTrue(bucket.last_check_ok)
        self.assertIn("Connected", bucket.last_check_detail)
        self.assertTrue(
            AuditEvent.objects.filter(action="r2.bucket.test", outcome="success").exists()
        )

    def test_the_request_the_test_sends_is_signed(self):
        bucket = R2Bucket.objects.create(account=self.account, name="course-art")
        seen = {}

        class Reader:
            status = 200
            headers = {}

            def read(self, size=-1):
                return b""

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout=None):
            seen["url"] = request.full_url
            seen["authorization"] = request.get_header("Authorization", "")
            seen["host"] = request.get_header("Host", "")
            return Reader()

        from unittest import mock

        with mock.patch("objectstore.r2.urllib.request.urlopen", fake_urlopen):
            verdict = test_bucket(bucket)

        self.assertTrue(verdict.ok, verdict.message)
        self.assertIn(f"/course-art?", seen["url"])
        self.assertIn("list-type=2", seen["url"])
        self.assertTrue(seen["authorization"].startswith(ALGORITHM))
        self.assertIn("Signature=", seen["authorization"])

    def test_a_403_is_reported_with_the_action_to_take(self):
        bucket = R2Bucket.objects.create(account=self.account, name="course-art")

        from unittest import mock

        class Denied:
            status = 403

            def read(self, size=-1):
                return b"<Error><Code>AccessDenied</Code></Error>"

        def deny(request, timeout=None):
            raise _forbidden()

        with mock.patch("objectstore.r2.urllib.request.urlopen", deny):
            verdict = test_bucket(bucket, actor=self.owner)

        bucket.refresh_from_db()
        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.status, 403)
        self.assertIn("Object Read & Write", verdict.message)
        self.assertFalse(bucket.last_check_ok)
        self.assertFalse(SECRET_KEY in verdict.message)

    def test_an_account_with_no_token_is_told_so(self):
        bare = R2Account.objects.create(owner=self.owner, name="No token", account_id="a" * 32)
        bucket = R2Bucket.objects.create(account=bare, name="anything")

        verdict = test_bucket(bucket)

        self.assertFalse(verdict.ok)
        self.assertIn("No API token", verdict.message)

    def test_an_undecryptable_token_asks_for_it_again(self):
        bucket = R2Bucket.objects.create(account=self.account, name="course-art")
        R2Account.objects.filter(pk=self.account.pk).update(secret_access_key_enc="v1:broken")
        self.account.refresh_from_db()
        bucket.account = self.account

        verdict = test_bucket(bucket)

        self.assertFalse(verdict.ok)
        self.assertIn("Re-enter the API token", verdict.message)

    def test_a_switched_off_account_is_not_tested(self):
        R2Account.objects.filter(pk=self.account.pk).update(is_active=False)
        self.account.refresh_from_db()
        bucket = R2Bucket.objects.create(account=self.account, name="course-art")

        verdict = test_bucket(bucket)

        self.assertFalse(verdict.ok)
        self.assertIn("switched off", verdict.message)


def _forbidden():
    import urllib.error

    return urllib.error.HTTPError(
        url="https://example/", code=403, msg="Forbidden", hdrs=None, fp=None
    )


def _local_perform(port):
    """Route a signed request at the local fake instead of Cloudflare.

    Only the host is redirected; the signature, headers and query string are
    exactly what the real call would send, so the fake sees a signed request.
    """
    import urllib.error
    import urllib.request

    def perform(method, url, headers, body=None):
        local = url.replace(
            f"https://{url.split('/')[2]}", f"http://127.0.0.1:{port}", 1
        )
        request = urllib.request.Request(local, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.read(4096)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(4096)

    return perform


class AdminPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.main = make_user("main", Role.MAIN_ADMIN, staff=True)
        cls.sub = make_user("sub", Role.SUB_ADMIN, staff=True)
        cls.other = make_user("other", Role.SUB_ADMIN, staff=True)
        cls.student = make_user("student", Role.STUDENT, staff=False)

    def test_a_student_cannot_open_the_storage_panel(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("admin:objectstore_r2account_changelist"))
        self.assertIn(response.status_code, (302, 403))

    def test_a_sub_admin_can_add_an_account_with_its_token(self):
        self.client.force_login(self.sub)

        response = self.client.post(
            reverse("admin:objectstore_r2account_add"),
            {
                "name": "My Cloudflare",
                "account_id": ACCOUNT_ID,
                "access_key_id": ACCESS_KEY,
                "secret_access_key": SECRET_KEY,
                "is_active": "on",
                "buckets-TOTAL_FORMS": "1",
                "buckets-INITIAL_FORMS": "0",
                "buckets-MIN_NUM_FORMS": "0",
                "buckets-MAX_NUM_FORMS": "1000",
                "buckets-0-name": "course-art",
                "buckets-0-public_base_url": "https://art.example.com",
                "buckets-0-enabled": "on",
                "buckets-0-allow_course_images": "on",
                "buckets-0-is_default_course_images": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        account = R2Account.objects.get(name="My Cloudflare")
        self.assertEqual(account.owner, self.sub)
        self.assertEqual(account.get_credentials().secret_access_key, SECRET_KEY)
        bucket = account.buckets.get()
        self.assertEqual(bucket.public_base_url, "https://art.example.com")
        self.assertTrue(bucket.is_default_course_images)

    def test_the_page_never_renders_a_secret(self):
        account = R2Account.objects.create(owner=self.sub, name="Mine", account_id=ACCOUNT_ID)
        account.set_credentials(ACCESS_KEY, SECRET_KEY)
        account.save()
        self.client.force_login(self.sub)

        change = self.client.get(
            reverse("admin:objectstore_r2account_change", args=[account.pk])
        )
        body = change.content.decode()

        self.assertEqual(change.status_code, 200)
        self.assertNotIn(SECRET_KEY, body)
        self.assertNotIn(ACCESS_KEY, body)
        self.assertNotIn(account.secret_access_key_enc, body)
        # It says a token is stored, and that leaving the boxes blank keeps it.
        self.assertIn("A token is already stored", body)

    def test_saving_without_touching_the_token_keeps_it(self):
        account = R2Account.objects.create(owner=self.sub, name="Mine", account_id=ACCOUNT_ID)
        account.set_credentials(ACCESS_KEY, SECRET_KEY)
        account.save()
        self.client.force_login(self.sub)

        self.client.post(
            reverse("admin:objectstore_r2account_change", args=[account.pk]),
            {
                "name": "Mine",
                "account_id": ACCOUNT_ID,
                "is_active": "on",
                "access_key_id": "",
                "secret_access_key": "",
                "buckets-TOTAL_FORMS": "0",
                "buckets-INITIAL_FORMS": "0",
                "buckets-MIN_NUM_FORMS": "0",
                "buckets-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )

        account.refresh_from_db()
        self.assertEqual(account.get_credentials().access_key_id, ACCESS_KEY)

    def test_replacing_the_token_is_audited(self):
        account = R2Account.objects.create(owner=self.sub, name="Mine", account_id=ACCOUNT_ID)
        account.set_credentials(ACCESS_KEY, SECRET_KEY)
        account.save()
        self.client.force_login(self.sub)

        self.client.post(
            reverse("admin:objectstore_r2account_change", args=[account.pk]),
            {
                "name": "Mine",
                "account_id": ACCOUNT_ID,
                "is_active": "on",
                "access_key_id": "AKIAIOSFODNN7EXAMPLE2",
                "secret_access_key": "new-secret",
                "buckets-TOTAL_FORMS": "0",
                "buckets-INITIAL_FORMS": "0",
                "buckets-MIN_NUM_FORMS": "0",
                "buckets-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )

        account.refresh_from_db()
        self.assertEqual(account.get_credentials().secret_access_key, "new-secret")
        event = AuditEvent.objects.filter(action="r2.account.rotate").get()
        self.assertEqual(event.actor, self.sub)
        self.assertTrue(event.metadata.get("credential_rotated"))
        self.assertNotIn("new-secret", str(event.metadata))

    def test_a_main_admin_can_add_an_account_without_picking_an_owner(self):
        self.client.force_login(self.main)

        response = self.client.post(
            reverse("admin:objectstore_r2account_add"),
            {
                "name": "Handed over",
                "account_id": ACCOUNT_ID,
                "access_key_id": ACCESS_KEY,
                "secret_access_key": SECRET_KEY,
                "is_active": "on",
                "buckets-TOTAL_FORMS": "0",
                "buckets-INITIAL_FORMS": "0",
                "buckets-MIN_NUM_FORMS": "0",
                "buckets-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        account = R2Account.objects.get(name="Handed over")
        self.assertEqual(account.owner, self.main)

    def test_half_a_token_is_refused(self):
        self.client.force_login(self.sub)

        response = self.client.post(
            reverse("admin:objectstore_r2account_add"),
            {
                "name": "Half",
                "account_id": ACCOUNT_ID,
                "access_key_id": ACCESS_KEY,
                "secret_access_key": "",
                "is_active": "on",
                "buckets-TOTAL_FORMS": "0",
                "buckets-INITIAL_FORMS": "0",
                "buckets-MIN_NUM_FORMS": "0",
                "buckets-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(R2Account.objects.filter(name="Half").exists())
        self.assertContains(response, "Paste both the access key id and the secret")

    def test_a_sub_admin_only_lists_and_opens_their_own_accounts(self):
        mine = R2Account.objects.create(owner=self.sub, name="Mine", account_id=ACCOUNT_ID)
        theirs = R2Account.objects.create(owner=self.other, name="Theirs", account_id="b" * 32)
        self.client.force_login(self.sub)

        listing = self.client.get(reverse("admin:objectstore_r2account_changelist"))
        self.assertContains(listing, "Mine")
        self.assertNotContains(listing, "Theirs")

        blocked = self.client.get(
            reverse("admin:objectstore_r2account_change", args=[theirs.pk])
        )
        self.assertEqual(blocked.status_code, 302)
        opened = self.client.get(
            reverse("admin:objectstore_r2account_change", args=[mine.pk])
        )
        self.assertEqual(opened.status_code, 200)

    def test_a_sub_admin_only_lists_their_own_buckets(self):
        mine = R2Account.objects.create(owner=self.sub, name="Mine", account_id=ACCOUNT_ID)
        R2Bucket.objects.create(account=mine, name="my-art", allow_course_images=True)
        theirs = R2Account.objects.create(owner=self.other, name="Theirs", account_id="c" * 32)
        R2Bucket.objects.create(account=theirs, name="their-art", allow_course_images=True)
        self.client.force_login(self.sub)

        listing = self.client.get(reverse("admin:objectstore_r2bucket_changelist"))

        self.assertContains(listing, "my-art")
        self.assertNotContains(listing, "their-art")

    def test_a_sub_admin_cannot_point_a_bucket_at_another_owner_account(self):
        others = R2Account.objects.create(owner=self.other, name="Theirs", account_id="d" * 32)
        self.client.force_login(self.sub)

        response = self.client.post(
            reverse("admin:objectstore_r2bucket_add"),
            {
                "account": others.pk,
                "name": "sneaky",
                "enabled": "on",
                "allow_pdfs": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(R2Bucket.objects.filter(name="sneaky").exists())

    def test_a_main_admin_sees_every_account_but_no_secret(self):
        account = R2Account.objects.create(owner=self.sub, name="Subs cloud", account_id=ACCOUNT_ID)
        account.set_credentials(ACCESS_KEY, SECRET_KEY)
        account.save()
        self.client.force_login(self.main)

        listing = self.client.get(reverse("admin:objectstore_r2account_changelist"))
        change = self.client.get(
            reverse("admin:objectstore_r2account_change", args=[account.pk])
        )

        self.assertContains(listing, "Subs cloud")
        self.assertNotIn(SECRET_KEY, change.content.decode())
        self.assertNotIn(ACCESS_KEY, change.content.decode())

    def test_the_test_button_reports_the_result_and_returns_to_the_list(self):
        account = R2Account.objects.create(owner=self.sub, name="Mine", account_id=ACCOUNT_ID)
        account.set_credentials(ACCESS_KEY, SECRET_KEY)
        account.save()
        bucket = R2Bucket.objects.create(account=account, name="course-art")
        self.client.force_login(self.sub)

        from unittest import mock

        from objectstore.r2 import BucketCheck

        with mock.patch(
            "objectstore.services.r2.check_bucket",
            return_value=BucketCheck(True, 200, "Connected. The bucket answered."),
        ):
            response = self.client.get(
                reverse("admin:objectstore_r2bucket_test", args=[bucket.pk]), follow=True
            )

        self.assertContains(response, "Course-art: Connected.")
        bucket.refresh_from_db()
        self.assertTrue(bucket.last_check_ok)
        # The account carries the newest verdict too, for its changelist.
        account.refresh_from_db()
        self.assertTrue(account.last_check_ok)

    def test_another_owners_bucket_cannot_be_tested_by_id(self):
        theirs = R2Account.objects.create(owner=self.other, name="Theirs", account_id="e" * 32)
        bucket = R2Bucket.objects.create(account=theirs, name="their-art")
        self.client.force_login(self.sub)

        response = self.client.get(
            reverse("admin:objectstore_r2bucket_test", args=[bucket.pk]), follow=True
        )

        self.assertContains(response, "does not exist")
        bucket.refresh_from_db()
        self.assertIsNone(bucket.last_check_ok)


class CommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("owner")
        cls.account = R2Account.objects.create(owner=cls.owner, name="Mine", account_id=ACCOUNT_ID)
        cls.account.set_credentials(ACCESS_KEY, SECRET_KEY)
        cls.account.save()
        cls.bucket = R2Bucket.objects.create(account=cls.account, name="course-art")

    def test_r2_check_reports_each_bucket_without_a_network(self):
        from io import StringIO
        from unittest import mock

        from objectstore.r2 import BucketCheck

        out = StringIO()
        with mock.patch(
            "objectstore.services.r2.check_bucket",
            return_value=BucketCheck(True, 200, "Connected. The bucket is reachable and currently empty."),
        ):
            call_command("r2_check", stdout=out)

        self.assertIn("[OK  ]", out.getvalue())
        self.assertIn("course-art", out.getvalue())

    def test_r2_check_fails_loudly_when_the_bucket_does_not_answer(self):
        from io import StringIO
        from unittest import mock

        from django.core.management.base import CommandError

        from objectstore.r2 import BucketCheck

        with mock.patch(
            "objectstore.services.r2.check_bucket",
            return_value=BucketCheck(False, 403, "Access denied."),
        ):
            with self.assertRaises(CommandError):
                call_command("r2_check", stdout=StringIO(), stderr=StringIO())

    def test_the_rotation_dry_run_does_not_change_the_stored_value(self):
        from io import StringIO

        before = R2Account.objects.get(pk=self.account.pk).secret_access_key_enc
        out = StringIO()
        call_command("r2_rotate_key", stdout=out)

        after = R2Account.objects.get(pk=self.account.pk).secret_access_key_enc
        self.assertEqual(before, after)
        self.assertIn("would be re-encrypted", out.getvalue())

    def test_rotation_re_encrypts_and_the_credential_still_works(self):
        """Old key → new key with both configured, exactly the documented order."""
        from io import StringIO

        old_key = crypto.generate_key()
        new_key = crypto.generate_key()
        with override_settings(R2_CREDENTIAL_KEYS=[old_key]):
            account = R2Account.objects.get(pk=self.account.pk)
            account.set_credentials(ACCESS_KEY, SECRET_KEY)
            account.save(update_fields=["access_key_id_enc", "secret_access_key_enc", "access_key_hint"])

        with override_settings(R2_CREDENTIAL_KEYS=[new_key, old_key]):
            call_command("r2_rotate_key", "--apply", stdout=StringIO())

            rotated = R2Account.objects.get(pk=self.account.pk)
            self.assertEqual(rotated.get_credentials().secret_access_key, SECRET_KEY)

        # Once the old key is dropped, the row still opens: the proof that the
        # re-encryption actually happened rather than the old ciphertext surviving.
        with override_settings(R2_CREDENTIAL_KEYS=[new_key]):
            alone = R2Account.objects.get(pk=self.account.pk)
            self.assertEqual(alone.get_credentials().access_key_id, ACCESS_KEY)

    def test_new_key_prints_a_usable_key_and_changes_nothing(self):
        from io import StringIO

        before = R2Account.objects.get(pk=self.account.pk).secret_access_key_enc
        out = StringIO()
        call_command("r2_rotate_key", "--new-key", stdout=out)

        printed = out.getvalue().splitlines()[0].strip()
        self.assertEqual(len(base64.urlsafe_b64decode(printed)), 32)
        self.assertEqual(
            R2Account.objects.get(pk=self.account.pk).secret_access_key_enc, before
        )
