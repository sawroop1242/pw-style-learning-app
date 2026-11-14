"""The console's stylesheet and the markup it styles, checked together.

A stylesheet is written against a document: this id is the page, that class is
the rail. When a template stops rendering one of those hooks, the CSS is still
valid, still parses, and still ships — it simply paints nothing. That is how
the top bar lost the navy block behind its name: the shell replaced Django's
header block, and the `#branding` wrapper Django draws inside it went with it,
leaving white text on a white bar.

These cases read both sides. The stylesheet is scanned the way a browser reads
it (id selectors, never the hex colours in declarations); the pages are read
the way a staff member sees them (the rendered response). A hook one side
names and the other does not have fails the test, with the page and the
selector named.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.html import parse_html

from accounts.models import Role
from courses.models import Course, CourseFolder, Lesson

User = get_user_model()

SHEET = Path(settings.BASE_DIR) / "static" / "staff" / "admin.css"

#: The stylesheet is linked with a content hash in production, so match the
#: path rather than a literal filename.
SHEET_LINK = re.compile(r'href="[^"]*staff/admin(?:\.\w+)?\.css"')

#: Ids the sheet paints that the shell removes on purpose. Each says why, so
#: the list stays a decision rather than a place to silence a failure.
REMOVED_ON_PURPOSE = {
    "user-tools": "replaced by the account menu",
    "breadcrumbs": "the trail lives in the top bar instead",
}

#: A token like `16203a` is a colour, not an id, even though it follows `#`.
HEX = re.compile(r"^[0-9a-fA-F]{3,8}$")


def selector_ids(css: str) -> set[str]:
    """Every `#id` used in a selector.

    Split at `{`: everything after the previous rule's closing brace and
    before the next opening one is a selector. Declarations are therefore
    never scanned, which is what keeps `color: #fff` out of the result.
    """
    found: set[str] = set()
    for chunk in css.split("{"):
        selector = chunk.rsplit("}", 1)[-1]
        for name in re.findall(r"#([A-Za-z][\w-]*)", selector):
            if not HEX.match(name):
                found.add(name)
    return found


def element_ids(html: str) -> dict[str, list[str]]:
    """`id -> [ancestor ids, outermost first]` for every element that has one."""
    found: dict[str, list[str]] = {}
    root = parse_html(html)

    def walk(element, ancestors: list[str]) -> None:
        for child in getattr(element, "children", []):
            if not hasattr(child, "name"):
                continue
            attributes = dict(child.attributes)
            identifier = attributes.get("id")
            if identifier:
                found[identifier] = list(ancestors)
            walk(child, ancestors + ([identifier] if identifier else []))

    walk(root, [])
    return found


class AdminStylesheetContractTests(TestCase):
    """Every screen the console shell draws, checked against its stylesheet."""

    #: A page from each shape the sheet styles: the dashboard, a list with
    #: filters, the add/edit/delete/history screens, and a plain form. The
    #: object screens are filled in from the created course rather than a
    #: literal id: PostgreSQL sequences are not rolled back with the test
    #: transaction, so on the database production uses the first course in a
    #: run is not necessarily the first one in this class.
    CONSOLE_PAGES = {
        "dashboard": "/admin/",
        "changelist": "/admin/courses/course/",
        "filtered list": "/admin/courses/course/?is_published__exact=1",
        "add form": "/admin/courses/course/add/",
        "change form": "/admin/courses/course/{pk}/change/",
        "history": "/admin/courses/course/{pk}/history/",
        "delete": "/admin/courses/course/{pk}/delete/",
        "password change": "/admin/password_change/",
    }

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="contract-admin", email="contract@example.com", password="TestPass123!"
        )
        cls.admin.profile.role = Role.MAIN_ADMIN
        cls.admin.profile.save()
        cls.course = Course.objects.create(
            title="Contract batch", slug="contract-batch", subject="Physics",
            is_published=True, owner=cls.admin,
        )
        folder = CourseFolder.objects.create(course=cls.course, title="Notes", position=0)
        Lesson.objects.create(course=cls.course, folder=folder, title="Class 1", position=0)

    def setUp(self):
        self.client.force_login(self.admin)

    def pages(self) -> dict[str, str]:
        return {label: url.format(pk=self.course.pk) for label, url in self.CONSOLE_PAGES.items()}

    def console(self, url: str) -> str:
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return response.content.decode()

    def test_every_screen_loads_the_stylesheet_in_the_head(self):
        for label, url in self.pages().items():
            with self.subTest(page=label):
                body = self.console(url)
                self.assertRegex(body, SHEET_LINK)
                # A stylesheet after <body> is still applied by browsers that
                # tolerate it, but it has already flashed unstyled content.
                self.assertLess(body.index("staff/admin"), body.index("<body"))

    def test_the_top_bar_keeps_the_wrapper_the_theme_paints(self):
        """`#branding` is what gets the navy block; the name sits inside it.

        The ancestor list is asserted exactly: a second nesting (or the
        wrapper moving inside `.ss-topbar-main`) would change the layout the
        stylesheet was written for, and should fail here rather than in a
        screenshot.
        """
        ids = element_ids(self.console("/admin/"))

        self.assertIn("branding", ids, "the top bar lost #branding")
        self.assertIn("site-name", ids)
        self.assertEqual(ids["site-name"], ["container", "header", "branding"])
        self.assertEqual(ids["branding"], ["container", "header"])

    def test_the_login_screen_has_the_brand_on_the_same_wrapper(self):
        """Signed out the header is the brand alone, still inside `#branding`."""
        client = self.client_class()
        ids = element_ids(client.get("/admin/login/").content.decode())

        self.assertIn("branding", ids)
        self.assertEqual(ids["site-name"], ["container", "header", "branding"])

    def test_the_stylesheet_names_nothing_the_screens_do_not_render(self):
        """The check that would have caught the missing wrapper.

        Every id the sheet styles must exist on at least one console screen,
        unless it is on the short, explained list above.
        """
        styled = selector_ids(SHEET.read_text())
        rendered: set[str] = set()
        for url in self.pages().values():
            rendered.update(element_ids(self.console(url)))

        missing = styled - rendered - set(REMOVED_ON_PURPOSE)
        self.assertEqual(
            missing,
            set(),
            "admin.css paints ids no console page renders: "
            + ", ".join(f"#{name}" for name in sorted(missing)),
        )

    def test_the_rail_and_the_top_bar_are_measured_by_their_outer_edge(self):
        """The geometry the rest of the shell offsets by depends on it.

        `--ss-rail` is what `#content-start` reserves and what the rail is
        told to be, and `--ss-topbar` is the padding `#main` takes. A padding
        or a border added on top of either number moves the painted edge away
        from the reserved one, so those boxes are border-box by contract.
        """
        css = SHEET.read_text()
        block = re.search(
            r"\.ss-admin #header,\s*\.ss-admin #branding,\s*\.ss-admin #nav-sidebar\s*"
            r"\{\s*box-sizing:\s*border-box;",
            css,
        )
        self.assertIsNotNone(block, "the border-box rule for the shell is missing")

        for token in ("--ss-rail: 248px", "--ss-topbar: 68px"):
            self.assertIn(token, css)
