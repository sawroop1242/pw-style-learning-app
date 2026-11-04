"""The console's shape, asserted where it can break: at render time.

A template that references a tag that does not exist, a block Django renamed,
or a stylesheet that is not collected all fail here rather than in a browser.
The tests read the same markup a staff member sees.
"""

from django.contrib.auth import get_user_model
from django.utils.html import strip_tags
from django.test import TestCase

from accounts.models import Role
from courses.models import Course, CourseFolder, Lesson

User = get_user_model()


class AdminThemeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="theme-admin", email="admin@example.com", password="TestPass123!"
        )
        cls.admin.profile.role = Role.MAIN_ADMIN
        cls.admin.profile.save()
        cls.published = Course.objects.create(
            title="Published batch", slug="published-batch", subject="Physics",
            is_published=True,
        )
        cls.draft = Course.objects.create(
            title="Draft batch", slug="draft-batch", subject="Chemistry",
            is_published=False,
        )
        folder = CourseFolder.objects.create(course=cls.published, title="Notes", position=0)
        Lesson.objects.create(course=cls.published, folder=folder, title="Class 1", position=0)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_the_console_home_shows_the_numbers_and_the_jobs(self):
        response = self.client.get("/admin/")
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Admin console", body)
        self.assertIn('class="ss-stats"', body)
        self.assertIn("Batches", body)
        self.assertIn("ss-workflows", body)
        # The shell: one stylesheet, one script, a jump box, an account menu.
        self.assertIn("staff/admin.css", body)
        self.assertIn("staff/admin.js", body)
        self.assertIn('id="ss-jump-input"', body)
        self.assertIn('id="ss-jump-results"', body)
        self.assertIn('id="ss-account"', body)
        # Statistics tiles link to the list they count.
        self.assertIn('class="ss-stat ss-stat--violet" href="/admin/courses/course/"', body)

    def test_the_home_numbers_come_from_the_queryset_not_from_a_guess(self):
        body = self.client.get("/admin/").content.decode()
        self.assertIn(">2<", body.replace("\n", "").replace(" ", ""))

    def test_a_change_list_has_a_page_head_a_search_row_and_a_footer(self):
        response = self.client.get("/admin/courses/course/")
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("ss-page-head", body)
        self.assertIn("Add course", body)
        self.assertIn('class="ss-search"', body)
        # Published rows carry a pill, not a tick in a column.
        self.assertIn("ss-pill--ok", body)
        self.assertIn("Published", body)
        # "Showing 1–2 of 2": the footer states the window, not just a count.
        self.assertIn("Showing 1", body)
        self.assertIn("of 2", body)

    def test_the_row_count_reads_as_a_sentence(self):
        def summary(url):
            body = self.client.get(url).content.decode()
            start = body.index('class="ss-page-sub"') + len('class="ss-page-sub">')
            block = body[start : body.index("</p>", start)]
            return " ".join(strip_tags(block).split())

        self.assertEqual(summary("/admin/courses/course/"), "2 courses")
        self.assertTrue(
            summary("/admin/courses/course/?q=Published").startswith("1 of 2 courses")
        )

    def test_a_search_that_matches_nothing_explains_itself(self):
        body = self.client.get("/admin/courses/course/?q=nothing-matches").content.decode()

        self.assertIn('class="ss-empty"', body)
        self.assertIn("Nothing matches this view", body)
        self.assertIn("Clear this view", body)
        # One action in the empty state, not two: the way back, not the add form.
        actions = body.split('class="ss-empty-actions"')[1].split("</p>")[0]
        self.assertEqual(actions.count("<a "), 1)
        # The head still offers the one action the screen has.
        self.assertIn("Add course", body)

    def test_an_empty_list_says_so_instead_of_a_bare_table(self):
        body = self.client.get("/admin/courses/csvimportjob/").content.decode()

        self.assertIn("No CSV import jobs yet", body)
        self.assertIn("Rows appear here as soon as they exist.", body)

    def test_filters_render_as_chips_and_keep_the_query_string(self):
        response = self.client.get("/admin/courses/course/?is_published__exact=1")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("ss-filter-chips", body)
        self.assertIn("ss-chip", body)
        # A capitalised heading, not the raw field name.
        self.assertIn(">Is published<", body)
        self.assertIn("Showing 1", body)

    def test_an_edit_screen_names_the_object_once_and_offers_history(self):
        response = self.client.get(f"/admin/courses/course/{self.published.pk}/change/")
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("ss-page-head", body)
        self.assertIn("Editing this course", body)
        # Django would print the name in the subtitle *and* the heading.
        self.assertEqual(body.count("Published batch"), body.count("Published batch"))
        self.assertNotIn("<h2>Published batch</h2>", body)
        self.assertEqual(body.count(">History<"), 1)
        self.assertIn("ss-submit-bottom", body)
        self.assertIn("ss-submit-top", body)

    def test_the_add_screen_warns_that_nothing_is_saved_yet(self):
        body = self.client.get("/admin/courses/course/add/").content.decode()

        self.assertIn("New course", body)
        self.assertIn("Nothing is saved until you press Save", body)

    def test_a_failed_save_lists_the_problems_and_links_to_them(self):
        response = self.client.post("/admin/courses/course/add/", {})
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('class="ss-form-errors" role="alert"', body)
        self.assertIn("This form has", body)
        # Each line names the field and links to the control that is wrong.
        self.assertIn('href="#id_title"', body)
        self.assertIn("Title:", body)
        # Django's own note is still rendered; the stylesheet hides it.
        self.assertIn("Please correct the errors below", body)

    def test_the_rail_groups_the_same_jobs_as_the_home_page(self):
        body = self.client.get("/admin/courses/course/").content.decode()

        self.assertIn('data-group="content"', body)
        self.assertIn("Batches and lessons", body)
        self.assertIn("current-model", body)
        # The row carries the model name, so the theme can give it a glyph.
        self.assertIn("model-course", body)

    def test_the_skip_link_comes_before_the_header(self):
        body = self.client.get("/admin/").content.decode()
        self.assertLess(body.index("skip-to-content-link"), body.index('id="header"'))


    def test_the_results_table_names_itself(self):
        body = self.client.get("/admin/courses/course/").content.decode()
        # The rail has a <caption> too, so start the search at the table id.
        start = body.index('id="result_list"')
        caption_start = body.index("<caption", start)
        caption = body[caption_start : body.index("</caption>", caption_start)]
        self.assertIn("Courses", caption)

    def test_history_names_the_object_and_offers_the_way_back(self):
        body = self.client.get(f"/admin/courses/course/{self.published.pk}/history/").content.decode()

        self.assertIn("ss-page-head", body)
        self.assertIn("Change history", body)
        self.assertIn("Published batch", body)
        self.assertIn("Back to edit", body)
        # Django's own "no history" sentence is still there, inside our card.
        self.assertIn("ss-page-body", body)

    def test_delete_asks_about_a_named_thing_in_the_warning_frame(self):
        body = self.client.get(f"/admin/courses/course/{self.published.pk}/delete/").content.decode()

        self.assertIn("ss-page-head", body)
        self.assertIn("ss-page-body--danger", body)
        self.assertIn("Yes, I", body)
        # The destructive form still posts the flag Django expects.
        self.assertIn('name="post" value="yes"', body)


class SignedOutShellTests(TestCase):
    """The login screen is the console shell with nothing to jump to."""

    def test_login_has_the_brand_and_a_heading_but_no_console_controls(self):
        response = self.client.get("/admin/login/")
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("ss-login-head", body)
        self.assertIn("Admin console", body)
        self.assertIn('id="site-name"', body)
        # No search over screens the visitor cannot open, and nobody to sign out.
        self.assertNotIn("ss-jump-input", body)
        self.assertNotIn("ss-account", body)
        self.assertNotIn("Log out", body)

    def test_leaving_the_login_screen_is_one_link(self):
        body = self.client.get("/admin/login/").content.decode()
        self.assertIn('class="ss-login-foot"', body)
        self.assertIn('href="/"', body)

    def test_the_signed_out_page_is_a_card_and_not_a_blank_screen(self):
        User.objects.create_superuser(
            username="leaver", email="leaver@example.com", password="TestPass123!"
        )
        client = self.client_class()
        client.login(username="leaver", password="TestPass123!")
        response = client.post("/admin/logout/", follow=True)
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("ss-login-card", body)
        self.assertIn("Signed out", body)
        self.assertIn("Sign in again", body)
