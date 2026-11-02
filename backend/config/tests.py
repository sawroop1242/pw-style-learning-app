"""The site is served by Django on a single-process host; this is the contract.

Before this existed the deployed URL answered a Django 404 at ``/``: the API and
the admin were reachable, the application itself was not.
"""

from django.test import TestCase

from config.views import FRONTEND_ROOT


class FrontendServingTests(TestCase):
    def test_home_page_is_the_app(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertContains(response, 'name="api-base" content="/api"')
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_every_page_loads(self):
        pages = [
            "index", "courses", "course", "tests", "test-player", "dashboard",
            "profile", "login", "community", "legal", "player",
            "offline", "splash",
        ]
        for name in pages:
            with self.subTest(page=name):
                response = self.client.get(f"/{name}.html")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

    def test_the_downloads_page_is_gone(self):
        """Downloads were removed outright — links must not survive to a 404."""
        self.assertEqual(self.client.get("/downloads.html").status_code, 404)
        self.assertEqual(self.client.get("/assets/js/downloads.js").status_code, 404)

    def test_stylesheets_and_scripts_are_served_with_their_own_type(self):
        for url, content_type in (
            ("/assets/css/tokens.css", "text/css; charset=utf-8"),
            ("/assets/js/core.js", "text/javascript; charset=utf-8"),
            ("/assets/icon.svg", "image/svg+xml; charset=utf-8"),
            ("/manifest.webmanifest", "application/manifest+json; charset=utf-8"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], content_type)

    def test_pages_are_never_stored(self):
        page = self.client.get("/courses.html")
        self.assertEqual(page["Cache-Control"], "no-store")

    def test_scripts_and_styles_are_revalidated_not_aged(self):
        """A deploy must not be served against last release's stylesheet.

        The URL carries no content hash, so an hour-long `max-age` here meant a
        returning visitor ran an old `course.js` against new HTML — which is
        exactly what happened after the run-31 deploy. They must revalidate,
        and revalidating must be cheap: a 304, not another copy.
        """
        for url in ("/assets/css/base.css", "/assets/js/core.js"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response["Cache-Control"], "no-cache")
                self.assertTrue(response["ETag"])
                self.assertTrue(response["Last-Modified"])

                again = self.client.get(url, HTTP_IF_NONE_MATCH=response["ETag"])
                self.assertEqual(again.status_code, 304)
                self.assertEqual(again.content, b"")

    def test_images_may_be_cached_for_an_hour(self):
        for url in ("/assets/icon.svg", "/assets/img/hero-art.jpg"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn("max-age", response["Cache-Control"])
                self.assertTrue(response["ETag"])

    def test_a_changed_file_gets_a_new_validator(self):
        import os

        url = "/assets/js/course.js"
        first = self.client.get(url)["ETag"]
        path = FRONTEND_ROOT / "assets/js/course.js"
        stat = path.stat()
        os.utime(path, (stat.st_atime, stat.st_mtime + 10))
        try:
            second = self.client.get(url)["ETag"]
        finally:
            os.utime(path, (stat.st_atime, stat.st_mtime))
        self.assertNotEqual(first, second)

    def test_service_worker_is_never_cached(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["Service-Worker-Allowed"], "/")

    def test_only_the_frontend_directory_is_reachable(self):
        for url in (
            "/config/settings.py",
            "/../manage.py",
            "/assets/../../backend/config/settings.py",
            "/assets/",
            "/readme.md",
            "/sw.js/../../config/urls.py",
        ):
            with self.subTest(url=url):
                # 302 is /admin/ redirecting to its login page, which is also
                # "not the front end" — the point is that no file leaks.
                self.assertIn(self.client.get(url).status_code, (302, 403, 404))

    def test_the_api_and_admin_still_own_their_prefixes(self):
        self.assertEqual(self.client.get("/api/").status_code, 200)
        self.assertIn(self.client.get("/admin/").status_code, (302, 200))
        self.assertEqual(self.client.get("/healthz/").status_code, 200)

    def test_head_requests_work(self):
        response = self.client.head("/")
        self.assertEqual(response.status_code, 200)

    def test_writes_are_not_allowed_on_static_files(self):
        self.assertEqual(self.client.post("/").status_code, 405)


class ReadinessTests(TestCase):
    """A deployment with a database it cannot reach must say so."""

    def test_ready_when_the_database_answers(self):
        response = self.client.get("/healthz/ready/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"], "ok")

    def test_unavailable_when_the_database_does_not(self):
        from unittest import mock

        with mock.patch("config.health.connection.cursor", side_effect=RuntimeError("no route to host")):
            response = self.client.get("/healthz/ready/")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["reason"], "RuntimeError")
        # The reason must be a class name, never a connection string.
        self.assertNotIn("postgres", str(payload).lower())

    def test_liveness_does_not_touch_the_database(self):
        from unittest import mock

        with mock.patch("config.health.connection.cursor", side_effect=RuntimeError("down")):
            response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)


class ContentSecurityPolicyTests(TestCase):
    """Audit finding 10: there was no Content-Security-Policy at all.

    Tokens live in browser storage, so an injected script is the worst outcome
    the app can have; the policy is what stops the browser running one.
    """

    def policy(self, url="/"):
        return self.client.get(url)["Content-Security-Policy"]

    def test_every_kind_of_response_carries_the_policy(self):
        for url in ("/", "/course.html", "/assets/js/core.js", "/assets/css/app.css", "/healthz/"):
            with self.subTest(url=url):
                self.assertTrue(self.policy(url), url)

    def test_scripts_may_only_come_from_this_origin(self):
        policy = self.policy()
        self.assertIn("script-src 'self';", policy)
        self.assertNotIn("'unsafe-eval'", policy)
        # The inline handlers and inline <script> blocks were removed so this
        # assertion can exist; if a page regresses, its console will say so.
        script_src = [part for part in policy.split(";") if part.strip().startswith("script-src")]
        self.assertNotIn("'unsafe-inline'", script_src[0])

    def test_the_rest_of_the_policy(self):
        policy = self.policy()
        for directive in (
            "default-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
        ):
            self.assertIn(directive, policy)

    def test_report_only_mode_replaces_the_enforcing_header(self):
        from django.test import override_settings

        with override_settings(CSP_REPORT_ONLY=True):
            response = self.client.get("/")
        self.assertEqual(response.get("Content-Security-Policy"), None)
        self.assertTrue(response.get("Content-Security-Policy-Report-Only"))

    def test_the_policy_can_be_replaced_without_a_code_change(self):
        """`CONTENT_SECURITY_POLICY` is an environment variable."""
        from django.test import override_settings

        with override_settings(CONTENT_SECURITY_POLICY="default-src 'none'"):
            self.assertEqual(self.policy(), "default-src 'none'")

    def test_no_page_carries_an_inline_script_or_handler(self):
        """A single inline block would be silently blocked by the policy."""
        import re

        pages = sorted(FRONTEND_ROOT.glob("*.html"))
        inline = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.IGNORECASE)
        handler = re.compile(r"\son(?:click|change|submit|load|error|input)\s*=", re.IGNORECASE)
        for page in pages:
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=page.name):
                self.assertIsNone(inline.search(text), f"{page.name} has an inline <script>")
                self.assertIsNone(handler.search(text), f"{page.name} has an inline handler")


class TokenLifetimeTests(TestCase):
    """Audit finding 9: the ADR's token settings were never in `settings.py`.

    SimpleJWT's defaults applied instead: a one-day refresh token with no
    rotation and no blacklisting, so a stolen refresh token could not be
    revoked. These tests hold the runtime settings to the ADR.
    """

    def test_settings_match_the_adr(self):
        from datetime import timedelta

        from django.conf import settings

        jwt = settings.SIMPLE_JWT
        self.assertEqual(jwt["ACCESS_TOKEN_LIFETIME"], timedelta(minutes=30))
        self.assertEqual(jwt["REFRESH_TOKEN_LIFETIME"], timedelta(days=7))
        self.assertTrue(jwt["ROTATE_REFRESH_TOKENS"])
        self.assertTrue(jwt["BLACKLIST_AFTER_ROTATION"])
        self.assertIn("rest_framework_simplejwt.token_blacklist", settings.INSTALLED_APPS)

    def test_refreshing_rotates_and_blacklists_the_old_token(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

        User = get_user_model()
        User.objects.create_user("rotator", "rotator@example.com", "SecurePass123!")
        client = APIClient()
        pair = client.post(
            "/api/token/",
            {"username_or_email": "rotator", "password": "SecurePass123!"},
            format="json",
        ).json()
        self.assertIn("refresh", pair)

        rotated = client.post("/api/token/refresh/", {"refresh": pair["refresh"]}, format="json")
        self.assertEqual(rotated.status_code, 200, rotated.content)
        self.assertIn("refresh", rotated.json(), "rotation must return a new refresh token")
        self.assertNotEqual(rotated.json()["refresh"], pair["refresh"])
        self.assertTrue(BlacklistedToken.objects.exists())

        # The rotated-away token cannot be used a second time.
        reused = client.post("/api/token/refresh/", {"refresh": pair["refresh"]}, format="json")
        self.assertEqual(reused.status_code, 401)


class ApiSchemaTests(TestCase):
    """The schema is generated from the code, and only staff may download it."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="schema-staff", password="TestPass123!", is_staff=True
        )
        cls.learner = User.objects.create_user(
            username="schema-learner", password="TestPass123!"
        )

    def test_staff_download_an_openapi_document_that_names_real_paths(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.staff)
        response = client.get("/api/schema/")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertTrue(body.startswith("openapi:") or body.startswith("openapi"))
        self.assertIn("/api/courses/", body)
        self.assertIn("/api/staff/uploads/", body)

    def test_a_learner_cannot_download_the_schema(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.learner)
        response = client.get("/api/schema/")
        self.assertIn(response.status_code, (401, 403))

    def test_an_anonymous_caller_cannot_download_the_schema(self):
        response = self.client.get("/api/schema/")
        self.assertIn(response.status_code, (401, 403))


class ApiVersionTests(TestCase):
    """Header versioning: today's clients are 1.0 without saying so."""

    def test_a_client_that_says_nothing_gets_version_1_0(self):
        response = self.client.get("/api/courses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")

    def test_a_client_may_pin_the_version_it_was_built_against(self):
        response = self.client.get(
            "/api/courses/", HTTP_ACCEPT="application/json; version=1.0"
        )
        self.assertEqual(response.status_code, 200)

    def test_an_unknown_version_is_refused_rather_than_guessed(self):
        response = self.client.get(
            "/api/courses/", HTTP_ACCEPT="application/json; version=99"
        )
        # 406, not a silent fallback: a client asking for a version this server
        # does not serve must be told, not answered in another dialect.
        self.assertEqual(response.status_code, 406)


class RequestIdTests(TestCase):
    """Every response carries an id, and a server error logs the same one."""

    def test_a_response_carries_an_id(self):
        response = self.client.get("/healthz/")
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_a_valid_upstream_id_is_passed_through(self):
        response = self.client.get("/healthz/", HTTP_X_REQUEST_ID="edge-abc12345")
        self.assertEqual(response["X-Request-ID"], "edge-abc12345")

    def test_a_header_that_is_not_an_id_is_replaced(self):
        # A newline here would split the log line, which is how log injection
        # starts. Anything that is not a boring id is ignored.
        for bad in ("short", "has space", "abc\ndef1234", "x" * 65):
            with self.subTest(value=bad):
                response = self.client.get("/healthz/", HTTP_X_REQUEST_ID=bad)
                self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_a_server_error_logs_the_id_it_returned(self):
        from django.http import HttpResponse

        from config.middleware import RequestIdMiddleware

        middleware = RequestIdMiddleware(lambda request: HttpResponse(status=500))
        with self.assertLogs("studyspace.requests", level="ERROR") as logs:
            response = middleware(self._request("/boom/", "trace-me-1234"))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response["X-Request-ID"], "trace-me-1234")
        self.assertIn("trace-me-1234", logs.output[0])
        self.assertIn("duration_ms", logs.output[0])

    def test_an_exception_is_logged_with_the_same_id_before_it_propagates(self):
        from config.middleware import RequestIdMiddleware

        def explode(request):
            raise RuntimeError("boom")

        middleware = RequestIdMiddleware(explode)
        request = self._request("/boom/", "trace-me-5678")
        with self.assertLogs("studyspace.requests", level="ERROR") as logs:
            with self.assertRaises(RuntimeError):
                middleware(request)

        self.assertIn("trace-me-5678", logs.output[0])

    def test_a_successful_request_is_not_logged_as_an_error(self):
        from django.http import HttpResponse

        from config.middleware import RequestIdMiddleware

        middleware = RequestIdMiddleware(lambda request: HttpResponse(status=200))
        with self.assertNoLogs("studyspace.requests", level="ERROR"):
            middleware(self._request("/healthz/"))

    @staticmethod
    def _request(path, request_id=None):
        from django.test import RequestFactory

        request = RequestFactory().get(path)
        if request_id is not None:
            request.META["HTTP_X_REQUEST_ID"] = request_id
        return request
