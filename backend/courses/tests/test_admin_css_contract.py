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


class DjangoDefaultOverrideTests(TestCase):
    """The theme has to *undo* Django's own layout, not merely add to it.

    Almost every defect this round had the same shape: `staff/admin.css` was
    correct, and Django's `base.css` / `login.css` / `responsive.css` sat
    underneath it with a rule the theme never cancelled — a `600px` width, a
    float, a white `.module` background, a column flex direction, a selector
    specific enough to win. The stylesheet parses, the markup is right, and
    the page is wrong.

    These cases read the theme against the Django it ships with, so removing
    one of the cancelling declarations fails here rather than in a screenshot.
    The rendered proof is `tools/checks/admin-render.js`; this is the cheap
    half that runs in the normal suite.
    """

    def setUp(self):
        self.css = SHEET.read_text()

    def rule(self, selector: str) -> str:
        """The declarations of the first rule whose selector list is exactly this."""
        pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
        match = re.search(pattern, self.css)
        self.assertIsNotNone(match, f"no rule for {selector!r}")
        return match.group(1)

    def assertDeclares(self, selector: str, declaration: str):
        body = re.sub(r"\s+", " ", self.rule(selector))
        self.assertIn(declaration, body, f"{selector!r} does not declare {declaration!r}")

    def test_the_dashboard_is_not_left_six_hundred_pixels_wide(self):
        """`base.css` pins `.dashboard #content { width: 600px }`.

        A grid laid over that keeps the 600px box: the work column collapses to
        the width of the stat tiles and the activity column floats outside the
        page. `width: auto` is what releases it, and `.colMS`'s 300px right
        margin has to go with it (the template sets `coltype` to `colMS`).
        """
        self.assertDeclares(".ss-admin.dashboard #content", "width: auto")
        self.assertDeclares(".ss-admin.dashboard #content.colMS", "margin-right: auto")
        self.assertDeclares(".ss-admin.dashboard #content-main", "float: none")
        self.assertDeclares(".ss-admin.dashboard #content-related", "float: none")
        self.assertDeclares(".ss-admin.dashboard #content-related", "margin-right: 0")

    def test_the_rail_does_not_get_the_card_surface(self):
        """`.module` is the card surface; the rail's groups are `div.module`."""
        # Selector lists are written across lines in the sheet; collapse them.
        rule = re.search(r"\.ss-admin #nav-sidebar \.module,(.*?)\{(.*?)\}", self.css, re.S)
        self.assertIsNotNone(rule, "the rail's surface reset is missing")
        self.assertIn(".ss-nav-group", rule.group(1))
        self.assertIn("background: transparent", rule.group(2))

    def test_the_login_screen_owns_its_backdrop(self):
        """A `:not()` chain out-specified the login rule and killed the navy.

        The guard rule is written with `:where()` so it contributes no
        specificity; without that, `body.ss-admin.login`'s radial gradient never
        applied and the white wordmark sat on flat canvas grey.
        """
        self.assertIn("body.ss-admin:where(.login)", self.css)
        self.assertDeclares("body.ss-admin.login", "radial-gradient")
        # Django's login.css makes `#container` a grey slab with `overflow: hidden`.
        self.assertDeclares("body.ss-admin.login #container", "background: transparent")
        self.assertDeclares("body.ss-admin.login #container", "overflow: visible")
        # Signed out, the wordmark sits on navy and has to stay white.
        self.assertIn("body.ss-admin.login #site-name a", self.css)
        self.assertIn("body.ss-admin.logged-out #site-name a", self.css)

    def test_the_list_card_is_not_sized_by_its_table(self):
        """`changelists.css` sets `align-items: flex-start` on the flex row.

        Stacked into a column, that means "shrink to max-content" — the card
        grew to the table's full width and the page scrolled sideways.
        """
        self.assertDeclares(".ss-admin #changelist", "align-items: stretch")

    def test_no_rule_depends_on_a_specificity_accident(self):
        """A bare `> input` cannot beat the desktop `> input[type="text"]`.

        The mobile stacked-form rule has to repeat the type selectors or it
        loses to the desktop rule it is meant to override — and `flex-basis`
        in a column is a *height*, which made every text input 320px tall.
        """
        pattern = re.compile(
            r"\.ss-admin \.aligned \.form-row \.flex-container > input\[type=\"text\"\][\s\S]{0,900}?"
            r"flex: 0 0 auto;"
        )
        self.assertRegex(self.css, pattern)
