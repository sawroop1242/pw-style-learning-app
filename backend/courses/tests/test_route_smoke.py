"""No route may answer with a server error.

Every page and every API route is reachable by somebody whose session we do
not control: a signed-out visitor, a student, a sub-admin. A 401, a 403, a 404
and a 405 are all correct answers to such a request — they say "not you", "no
such thing", "not that verb". A **500** is never correct: it means the request
reached code that raised.

The cases below do not list the routes by hand. A hand-written list stops
covering the route added last week; these walk the URLconf itself, so a new
view is exercised the moment it is registered, and a failure names the exact
path that blew up and the identity that asked for it.

Both halves matter. An empty database is the easy case — a queryset over
nothing rarely raises. The second case seeds the demo catalogue and enrols the
student in it first, because the bugs that reach the browser are the ones a
serializer hits when it follows a relation into real rows.
"""

from __future__ import annotations

import re
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import Course, Quiz

User = get_user_model()

#: Resolvers skipped, with the reason. Both are covered by their own tests and
#: would only be re-walked here for no new signal.
SKIP_NAMESPACES = {
    "admin": "Django admin, covered by test_admin",
}

#: Query strings the pages really send, and the versions a learner can produce
#: by editing the address bar or arriving from I package a stale link. None of
#: them may reach a view that raises.
QUERY_CASES = [
    # What the screens ask for.
    ("/api/courses/?page_size=12", "catalogue"),
    ("/api/courses/?mine=1&page_size=20", "my batches"),
    ("/api/courses/?slug=demo-jee-main-2027&page_size=1", "one batch by slug"),
    ("/api/courses/facets/", "the filter panel"),
    ("/api/lessons/?page_size=60", "lesson list"),
    ("/api/lessons/?course=1&page_size=60", "lessons of one batch"),
    ("/api/pdfs/?course=1&page_size=60", "notes of one batch"),
    ("/api/quizzes/?page_size=60", "test list"),
    ("/api/quizzes/?course=1&page_size=50", "tests of one batch"),
    ("/api/community/?page_size=40", "announcements"),
    ("/api/community/?course=1&page_size=10", "announcements of one batch"),
    ("/api/progress/?page_size=60&ordering=-updated_at", "recent progress"),
    ("/api/progress/?completed=1&page_size=1", "completed count"),
    ("/api/notes/?page_size=10", "notes"),
    ("/api/quiz-attempts/?page_size=20", "attempts"),
    ("/api/study-tasks/?page_size=20", "planner"),
    ("/api/schedule/?days=30", "timetable"),
    ("/api/insights/topics/?course=1", "weak topics"),
    ("/api/notifications/", "notifications"),
    # What a mistyped address asks for.
    ("/api/courses/?page=abc", "page is not a number"),
    ("/api/courses/?page=-1", "negative page"),
    ("/api/courses/?page=9999", "page past the end"),
    ("/api/courses/?page_size=99999", "absurd page size"),
    ("/api/courses/?ordering=bogus", "unknown ordering"),
    ("/api/courses/?course=abc", "course id is not a number"),
    ("/api/lessons/?course=abc", "lesson filter is not a number"),
    ("/api/community/?search=%3Cscript%3E", "search is a tag"),
    ("/api/insights/topics/?course=abc", "insights filter is not a number"),
    ("/api/schedule/?days=abc", "days is not a number"),
    ("/api/schedule/?days=999999", "absurd day count"),
]


def _concrete(pattern: str) -> str | None:
    """A concrete URL for a pattern, or ``None`` when it is not one URL."""
    text = str(pattern).strip()
    # Routers are included with a prefix of their own, so an anchor can appear
    # in the middle of the concatenated path: `/api/` + `^courses/$`.
    text = text.replace("^", "")
    if text.endswith("$"):
        text = text[:-1]
    if text.endswith("/?"):
        text = text[:-2]

    # The `?format=` variants duplicate the plain route they decorate.
    if "(?P<format>" in text:
        return None

    # A named group carries one value — `(?P<pk>[^/.]+)` for a router lookup,
    # `(?P<id>\\d+)` for a hand-written one. Anything more elaborate (the
    # site's own asset pattern, with alternatives inside the group) is not a
    # single URL, and substituting a value would invent a path no view serves.
    groups = re.findall(r"\(\?P<[a-zA-Z_]+>([^()]*)\)", text)
    simple = re.compile(r"\[\^?[^\]]*\]\+?|[a-z0-9]+|\\d\+")
    if any(not simple.fullmatch(group) for group in groups):
        return None

    # Each one becomes a value that cannot exist, so a detail route reaches its
    # view and answers 404 rather than failing to match at all.
    text = re.sub(r"\(\?P<[a-zA-Z_]+>[^()]*\)", "1", text)

    # What is left is a pattern with alternatives or a character class of its
    # own — the site's asset regex, not a route anybody can name.
    if any(char in text for char in "()[]|+*"):
        return None

    text = text.replace(r"\.", ".").replace("\\", "/")
    return re.sub(r"/+", "/", "/" + text.strip("/") + "/")


def routes(resolver=None, prefix: str = "/") -> list[tuple[str, str]]:
    """(name, concrete path) for every URL that is a single path."""
    resolver = resolver or get_resolver()
    found: list[tuple[str, str]] = []
    for entry in resolver.url_patterns:
        if isinstance(entry, URLResolver):
            if (entry.namespace or "") in SKIP_NAMESPACES:
                continue
            found.extend(routes(entry, prefix + str(entry.pattern)))
        elif isinstance(entry, URLPattern):
            path = _concrete(prefix + str(entry.pattern))
            if path is not None:
                found.append((entry.name or str(entry.pattern), path))
    return found


class RouteSmokeMixin:
    """The identities, the walk and the query matrix, shared by both cases."""

    @classmethod
    def make_user(cls, name, *, role=Role.STUDENT, staff=False):
        user = User.objects.create_user(
            username=name,
            email=f"{name}@example.com",
            password="TestPass123!",
            is_staff=staff,
        )
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        # A throttle window is stored in the cache and would otherwise carry
        # across tests: this case makes a few hundred requests in a second and
        # would leave every later test in the run answering 429.
        cache.clear()

    def tearDown(self):
        cache.clear()

    def get(self, client, path):
        """One request with an empty throttle window."""
        cache.clear()
        return client.get(path)

    def clients(self):
        # `raise_request_exception=False` turns a 500 into a response instead of
        # an exception, so the failure names every offending path at once rather
        # than stopping at the first one.
        def make(user=None):
            client = APIClient(raise_request_exception=False)
            if user is not None:
                client.force_authenticate(user=user)
            return client

        return {
            "anonymous": make(),
            "student": make(self.student),
            "sub-admin": make(self.staff),
        }

    def server_errors(self):
        """Every 5xx, as ``role GET path (route name) → status``."""
        failures = []
        for role, client in self.clients().items():
            for name, path in routes():
                response = self.get(client, path)
                if response.status_code >= 500:
                    failures.append(f"{role} GET {path} ({name}) → {response.status_code}")
        return sorted(set(failures))

    def assert_no_server_errors(self):
        failures = self.server_errors()
        self.assertEqual(failures, [], "routes raised:\n  " + "\n  ".join(failures))

    def test_no_query_string_returns_a_server_error(self):
        """The address bar is user input: a bad value is a 4xx, never a 500."""
        failures = []
        for role, client in self.clients().items():
            for path, label in QUERY_CASES:
                response = self.get(client, path)
                if response.status_code >= 500:
                    failures.append(f"{role} GET {path} ({label}) → {response.status_code}")
        self.assertEqual(failures, [], "queries raised:\n  " + "\n  ".join(failures))


class RouteSmokeTest(RouteSmokeMixin, TestCase):
    """The routes on an empty database."""

    @classmethod
    def setUpTestData(cls):
        cls.student = cls.make_user("smoke_student")
        cls.staff = cls.make_user("smoke_staff", role=Role.SUB_ADMIN, staff=True)

    def test_the_walk_finds_the_routes(self):
        """Guard the guard: an empty or truncated walk would pass silently."""
        paths = {path for _, path in routes()}
        self.assertGreater(len(paths), 50, f"only found {len(paths)} routes")
        for expected in (
            "/api/courses/",
            "/api/courses/1/",
            "/api/quizzes/1/",
            "/api/staff/courses/",
            "/api/auth/me/",
            "/healthz/",
        ):
            self.assertIn(expected, paths, f"{expected} missing from the URLconf walk")

    def test_is_actually_walking_the_viewsets(self):
        """A router that stopped expanding would leave 90 checks untested."""
        names = {name for name, _ in routes()}
        for expected in (
            "course-list",
            "course-detail",
            "start-quiz-attempt",
            "quiz-attempt-result",
            "staff-course-list",
        ):
            self.assertIn(expected, names)

    def test_no_route_returns_a_server_error(self):
        self.assert_no_server_errors()

    def test_no_query_string_returns_a_server_error(self):
        """The address bar is user input: a bad value is a 4xx, never a 500."""
        failures = []
        for role, client in self.clients().items():
            for path, label in QUERY_CASES:
                response = self.get(client, path)
                if response.status_code >= 500:
                    failures.append(f"{role} GET {path} ({label}) → {response.status_code}")
        self.assertEqual(failures, [], "queries raised:\n  " + "\n  ".join(failures))

    def test_every_page_is_served(self):
        """The pages the app links to are files the server returns as HTML."""
        pages = [
            "index.html", "courses.html", "course.html", "subject.html",
            "learn.html", "tests.html", "test-player.html", "player.html",
            "pdf.html", "community.html", "profile.html", "splash.html",
            "dashboard.html", "login.html", "legal.html", "offline.html",
        ]
        client = APIClient()
        for page in pages:
            with self.subTest(page=page):
                response = client.get(f"/{page}")
                self.assertEqual(response.status_code, 200, page)
                self.assertIn("text/html", response["Content-Type"], page)

    def test_unknown_page_and_asset_are_not_server_errors(self):
        client = APIClient()
        self.assertEqual(client.get("/nope.html").status_code, 404)
        self.assertEqual(client.get("/assets/css/nope.css").status_code, 404)
        # The directory itself is not browsable.
        self.assertEqual(client.get("/assets/").status_code, 404)


class RouteSmokeWithDataTest(RouteSmokeMixin, TestCase):
    """The same walk with the demo catalogue behind it, and a learner enrolled.

    This is the case that matches production: the pages the user opens are
    rendered from published courses, folders, lessons, notes and papers that
    actually exist. A serializer that trips over a null relation, an empty
    folder or a question without choices fails here and nowhere else.
    """

    @classmethod
    def setUpTestData(cls):
        cls.student = cls.make_user("seeded_student")
        cls.staff = cls.make_user("seeded_staff", role=Role.SUB_ADMIN, staff=True)
        call_command("seed_demo", stdout=StringIO())

        client = APIClient()
        client.force_authenticate(user=cls.student)
        for course in Course.objects.filter(is_published=True):
            # The same call the "Join" button makes. Paid batches answer 400,
            # which is correct and is not what this case is about.
            client.post(f"/api/courses/{course.id}/enroll/")
        for quiz in Quiz.objects.filter(is_published=True)[:5]:
            client.post("/api/quizzes/start/", {"quiz_id": quiz.id}, format="json")

    def test_no_route_returns_a_server_error(self):
        self.assert_no_server_errors()

    def test_the_seeded_pages_have_something_to_render(self):
        """Guard the fixture: an empty seed would make the case above vacuous."""
        self.assertTrue(Course.objects.filter(is_published=True).exists())
        self.assertTrue(Quiz.objects.filter(is_published=True).exists())

    def test_an_enrolled_student_gets_the_batch_detail(self):
        client = APIClient()
        client.force_authenticate(user=self.student)
        for course in Course.objects.filter(is_published=True):
            with self.subTest(course=course.slug):
                response = client.get(f"/api/courses/{course.id}/")
                self.assertEqual(response.status_code, 200)
                self.assertIn("folders", response.json())
