"""The console's shape, asserted where it can break: at render time.

A template that references a tag that does not exist, a block Django renamed,
or a stylesheet that is not collected all fail here rather than in a browser.
The tests read the same markup a staff member sees.
"""

from django.contrib.auth import get_user_model
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
        # The shell: one stylesheet, one script, a jump box, an account chip.
        self.assertIn("staff/admin.css", body)
        self.assertIn("staff/admin.js", body)
        self.assertIn('id="ss-jump-input"', body)
        self.assertIn('class="ss-account"', body)

    def test_the_heading_counts_come_from_the_queryset_not_from_a_guess(self):
        body = self.client.get("/admin/").content.decode()
        compact = body.replace("\n", "").replace(" ", "")
        self.assertIn(">2<", compact)

    def test_a_change_list_has_a_page_head_a_primary_action_and_a_footer(self):
        response = self.client.get("/admin/courses/course/")
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("ss-page-head", body)
        self.assertIn("Add course", body)
        # Published rows carry a pill, not a tick in a column.
        self.assertIn("ss-pill--ok", body)
        self.assertIn("Published", body)
        # "Showing 1–2 of 2": the footer states the window, not just a count.
        self.assertIn("Showing 1", body)
        self.assertIn("of 2", body)

    def test_filters_render_as_chips_and_keep_the_query_string(self):
        response = self.client.get("/admin/courses/course/?is_published__exact=1")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("ss-filter-chips", body)
        self.assertIn("ss-chip", body)
        self.assertIn("Showing 1", body)

    def test_an_edit_screen_says_what_is_being_edited_and_offers_history(self):
        response = self.client.get(f"/admin/courses/course/{self.published.pk}/change/")
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("ss-page-head", body)
        self.assertIn("Published batch", body)
        self.assertIn("History", body)
        self.assertIn("submit-row", body)

    def test_the_add_screen_warns_that_nothing_is_saved_yet(self):
        body = self.client.get("/admin/courses/course/add/").content.decode()
        self.assertIn("Nothing is saved until you press Save", body)

    def test_the_rail_groups_the_same_jobs_as_the_home_page(self):
        body = self.client.get("/admin/courses/course/").content.decode()
        self.assertIn('data-group="content"', body)
        self.assertIn("Batches and lessons", body)
        # The current screen is marked, and a screen the user may add to has a +.
        self.assertIn("current-model", body)
