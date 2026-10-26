"""The site is served by Django on a single-process host; this is the contract.

Before this existed the deployed URL answered a Django 404 at ``/``: the API and
the admin were reachable, the application itself was not.
"""

from django.test import TestCase


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
            "downloads", "profile", "login", "community", "legal", "player",
            "offline", "splash",
        ]
        for name in pages:
            with self.subTest(page=name):
                response = self.client.get(f"/{name}.html")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

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

    def test_static_assets_are_cacheable_but_pages_are_not(self):
        asset = self.client.get("/assets/css/base.css")
        self.assertIn("max-age", asset["Cache-Control"])

        page = self.client.get("/courses.html")
        self.assertEqual(page["Cache-Control"], "no-store")

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
