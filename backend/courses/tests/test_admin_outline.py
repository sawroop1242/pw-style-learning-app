"""The batch outline: the order of sections and classes, saved as a whole.

Two kinds of test here. The first group drives the screen a staff member opens —
who may see it, what it says, and what a save does. The second drives the order
itself through `courses.outline`: every way a payload can be wrong, and the
guarantee that a refused save changes nothing.

The rules the payload has to satisfy are the product decisions: it names every
section and every class exactly once, in order; a class may move between
sections; and the revision it was built from must still be current.
"""

import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Role
from courses.models import Course, CourseFolder, Lesson
from courses.outline import OutlineError, apply_order, build_outline, revision_of

User = get_user_model()


class OutlineFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="outline-admin", email="outline@example.com", password="TestPass123!"
        )
        cls.admin.profile.role = Role.MAIN_ADMIN
        cls.admin.profile.save()

        cls.provider = User.objects.create_user(
            username="outline-provider", email="provider@example.com",
            password="TestPass123!", is_staff=True,
        )
        cls.provider.profile.role = Role.SUB_ADMIN
        cls.provider.profile.save()

        cls.colleague = User.objects.create_user(
            username="outline-colleague", email="colleague@example.com",
            password="TestPass123!", is_staff=True,
        )
        cls.colleague.profile.role = Role.SUB_ADMIN
        cls.colleague.profile.save()

        cls.student = User.objects.create_user(
            username="outline-student", email="student@example.com", password="TestPass123!"
        )

        cls.course = Course.objects.create(
            title="Mechanics 2027", slug="mechanics-2027", owner=cls.provider, is_published=True
        )
        cls.other_course = Course.objects.create(
            title="Optics 2027", slug="optics-2027", owner=cls.colleague, is_published=True
        )

        cls.section_one = CourseFolder.objects.create(course=cls.course, title="Units", position=0)
        cls.section_two = CourseFolder.objects.create(course=cls.course, title="Motion", position=1)

        cls.lesson_a = Lesson.objects.create(
            course=cls.course, folder=cls.section_one, title="Measurement", position=0, duration_minutes=42,
        )
        cls.lesson_b = Lesson.objects.create(
            course=cls.course, folder=cls.section_one, title="Errors", position=1,
        )
        cls.lesson_c = Lesson.objects.create(
            course=cls.course, folder=cls.section_two, title="Velocity", position=0, is_published=True,
        )

        foreign_section = CourseFolder.objects.create(course=cls.other_course, title="Lenses", position=0)
        cls.foreign_lesson = Lesson.objects.create(
            course=cls.other_course, folder=foreign_section, title="Focal length", position=0,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    @property
    def url(self):
        return reverse("admin:courses_course_outline", args=[self.course.pk])

    def payload(self, sections, revision=None):
        body = {"sections": sections}
        if revision is not None:
            body["revision"] = revision
        return body

    def post(self, body):
        return self.client.post(
            self.url, data=json.dumps(body), content_type="application/json"
        )

    def current_revision(self):
        return revision_of(build_outline(self.course))


class OutlineScreenTests(OutlineFixture):
    def test_the_screen_lists_every_section_and_class_in_order(self):
        response = self.client.get(self.url)
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mechanics 2027")
        # Sections first, then their classes, in position order.
        self.assertLess(body.index("Units"), body.index("Measurement"))
        self.assertLess(body.index("Measurement"), body.index("Errors"))
        self.assertLess(body.index("Motion"), body.index("Velocity"))
        self.assertIn("2 sections and 3 classes", body)

    def test_every_row_has_a_handle_and_arrows_not_only_a_drag(self):
        """The non-dragging path is the accessibility requirement, not a bonus."""
        body = self.client.get(self.url).content.decode()

        self.assertEqual(body.count("data-outline-handle"), 5)  # 2 sections + 3 classes
        # The section's own arrows live in the head; the script disables them at
        # the ends of the list, so the head has to be marked.
        self.assertEqual(body.count("data-outline-head"), 2)
        self.assertIn('data-outline-move="up"', body)
        self.assertIn('data-outline-move="down"', body)
        # Every class can be moved to another section without dragging it.
        self.assertEqual(body.count("data-outline-pick"), 3)
        self.assertIn("No section", body)

    def test_the_markup_carries_every_hook_the_script_reads(self):
        """`tools/checks/outline.js` drives a fixture built from this contract.

        The fixture cannot see this template, so the contract is asserted here:
        a marker renamed in the HTML and not in the script would leave the
        screen silently inert.
        """
        body = self.client.get(self.url).content.decode()
        for hook in (
            "data-outline ",
            "data-outline-sections",
            "data-outline-section ",
            "data-outline-head",
            "data-outline-list",
            "data-outline-lesson",
            "data-outline-handle",
            "data-outline-move=\"up\"",
            "data-outline-move=\"down\"",
            "data-outline-pick",
            "data-outline-save",
            "data-outline-reset",
            "data-save-url=",
            "data-revision=",
            'id="outline-status"',
            "csrfmiddlewaretoken",
        ):
            self.assertIn(hook, body, hook)

    def test_the_screen_carries_the_revision_it_was_built_from(self):
        response = self.client.get(self.url)
        self.assertIn(f'data-revision="{self.current_revision()}"', response.content.decode())
        self.assertIn("csrfmiddlewaretoken", response.content.decode())

    def test_save_starts_disabled_and_undo_starts_disabled(self):
        body = self.client.get(self.url).content.decode()
        self.assertIn('data-outline-save disabled', body)
        self.assertIn('data-outline-reset disabled', body)

    def test_a_batch_with_no_sections_says_so_instead_of_drawing_nothing(self):
        empty = Course.objects.create(
            title="Empty batch", slug="empty-batch", owner=self.provider, is_published=False
        )
        response = self.client.get(reverse("admin:courses_course_outline", args=[empty.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This batch has no sections yet")
        self.assertNotContains(response, "data-outline-save")

    def test_the_batch_form_links_to_the_outline(self):
        response = self.client.get(reverse("admin:courses_course_change", args=[self.course.pk]))
        self.assertContains(response, reverse("admin:courses_course_outline", args=[self.course.pk]))
        self.assertContains(response, "Arrange classes and sections")


class OutlineAccessTests(OutlineFixture):
    def test_a_sub_admin_may_open_their_own_batch_outline(self):
        self.client.force_login(self.provider)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_a_sub_admin_gets_a_404_for_a_colleagues_batch(self):
        # The same answer the change form gives: the row is not theirs, and a
        # different error would confirm that the batch exists.
        self.client.force_login(self.colleague)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_a_sub_admin_cannot_save_a_colleagues_batch(self):
        self.client.force_login(self.colleague)
        response = self.post(self.payload([{"folder": self.section_one.pk, "lessons": []}]))
        self.assertEqual(response.status_code, 404)

    def test_a_signed_out_visitor_is_sent_to_the_login_page(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_a_student_cannot_open_the_outline(self):
        self.client.force_login(self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_a_non_numeric_id_is_a_404_not_a_server_error(self):
        response = self.client.get(reverse("admin:courses_course_outline", args=["not-a-number"]))
        self.assertEqual(response.status_code, 404)

    def test_the_save_is_not_csrf_exempt(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(
            self.url,
            data=json.dumps(self.payload([{"folder": self.section_one.pk, "lessons": []}])),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


class OutlineSaveTests(OutlineFixture):
    def ordered(self, sections):
        """Sections as the payload wants them, with the revision added."""
        return self.post(self.payload(sections, revision=self.current_revision()))

    def test_reordering_sections_saves_their_new_positions(self):
        response = self.ordered(
            [
                {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
                {"folder": self.section_one.pk, "lessons": [self.lesson_b.pk, self.lesson_a.pk]},
            ]
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        self.section_two.refresh_from_db()
        self.section_one.refresh_from_db()
        self.lesson_a.refresh_from_db()
        self.lesson_b.refresh_from_db()
        self.assertEqual(self.section_two.position, 0)
        self.assertEqual(self.section_one.position, 1)
        # Classes move with their section, and their own order is respected.
        self.assertEqual(self.lesson_b.position, 0)
        self.assertEqual(self.lesson_a.position, 1)

        order = [section.title for section in build_outline(self.course)]
        self.assertEqual(order, ["Motion", "Units"])

    def test_a_class_can_move_between_sections(self):
        response = self.ordered(
            [
                {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk]},
                {"folder": self.section_two.pk, "lessons": [self.lesson_b.pk, self.lesson_c.pk]},
            ]
        )
        self.assertEqual(response.status_code, 200)

        self.lesson_b.refresh_from_db()
        self.assertEqual(self.lesson_b.folder_id, self.section_two.pk)
        self.assertEqual(self.lesson_b.position, 0)
        self.lesson_c.refresh_from_db()
        self.assertEqual(self.lesson_c.position, 1)

    def test_a_class_with_no_section_is_listed_last_and_can_be_put_back(self):
        self.lesson_b.folder = None
        self.lesson_b.position = 0
        self.lesson_b.save(update_fields=["folder", "position"])

        titles = [section.title for section in build_outline(self.course)]
        self.assertEqual(titles, ["Units", "Motion", "No section"])

        response = self.ordered(
            [
                {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk]},
                {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
                {"folder": None, "lessons": [self.lesson_b.pk]},
            ]
        )
        self.assertEqual(response.status_code, 200)
        self.lesson_b.refresh_from_db()
        self.assertIsNone(self.lesson_b.folder_id)

    def test_the_response_returns_the_order_and_its_new_revision(self):
        response = self.ordered(
            [
                {"folder": self.section_one.pk, "lessons": [self.lesson_b.pk, self.lesson_a.pk]},
                {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
            ]
        )
        data = response.json()
        self.assertEqual(data["revision"], self.current_revision())
        self.assertEqual(data["sections"][0]["lessons"][0]["title"], "Errors")
        self.assertIn("Saved", data["message"])

    def test_saving_the_same_order_writes_no_history_entry(self):
        before = LogEntry.objects.count()
        response = self.ordered(
            [
                {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk, self.lesson_b.pk]},
                {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
            ]
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LogEntry.objects.count(), before)

    def test_a_real_move_lands_in_the_batch_history(self):
        self.ordered(
            [
                {"folder": self.section_one.pk, "lessons": [self.lesson_b.pk, self.lesson_a.pk]},
                {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
            ]
        )
        entry = LogEntry.objects.filter(object_id=str(self.course.pk)).first()
        self.assertIsNotNone(entry)
        self.assertIn("Reordered the outline", entry.change_message)

    def test_the_other_batch_is_untouched(self):
        before = list(
            Lesson.objects.filter(course=self.other_course).values_list("pk", "folder_id", "position")
        )
        self.ordered(
            [
                {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
                {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk, self.lesson_b.pk]},
            ]
        )
        after = list(
            Lesson.objects.filter(course=self.other_course).values_list("pk", "folder_id", "position")
        )
        self.assertEqual(before, after)


class OutlineRefusalTests(OutlineFixture):
    def assert_refused(self, body, status=400, code=None):
        before = list(
            CourseFolder.objects.filter(course=self.course).values_list("pk", "position")
        )
        lessons_before = list(Lesson.objects.filter(course=self.course).values_list("pk", "folder_id", "position"))

        response = self.post(body)
        self.assertEqual(response.status_code, status, response.content.decode())
        if code:
            self.assertEqual(response.json()["error"], code)
        self.assertTrue(response.json()["message"])

        # Refused means unchanged — a half-applied order is the failure this
        # endpoint exists to prevent.
        self.assertEqual(
            before, list(CourseFolder.objects.filter(course=self.course).values_list("pk", "position"))
        )
        self.assertEqual(
            lessons_before,
            list(Lesson.objects.filter(course=self.course).values_list("pk", "folder_id", "position")),
        )
        return response

    def test_a_stale_revision_is_refused_with_409(self):
        response = self.assert_refused(
            self.payload(
                [
                    {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
                    {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk, self.lesson_b.pk]},
                ],
                revision="0000000000000000",
            ),
            status=409,
            code="conflict",
        )
        self.assertIn("Reload", response.json()["message"])

    def test_a_class_from_another_batch_is_refused(self):
        self.assert_refused(
            self.payload(
                [
                    {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk, self.lesson_b.pk, self.foreign_lesson.pk]},
                    {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
                ]
            ),
            code="stale",
        )

    def test_a_missing_class_is_refused_rather_than_left_behind(self):
        self.assert_refused(
            self.payload(
                [
                    {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk]},
                    {"folder": self.section_two.pk, "lessons": []},
                ]
            ),
            code="stale",
        )

    def test_a_class_listed_twice_is_refused(self):
        self.assert_refused(
            self.payload(
                [
                    {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk, self.lesson_b.pk]},
                    {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk, self.lesson_b.pk]},
                ]
            )
        )

    def test_a_section_that_is_not_in_this_batch_is_refused(self):
        foreign_section = CourseFolder.objects.filter(course=self.other_course).first()
        self.assert_refused(
            self.payload(
                [
                    {"folder": foreign_section.pk, "lessons": [self.lesson_a.pk]},
                    {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
                ]
            ),
            code="stale",
        )

    def test_a_section_listed_twice_is_refused(self):
        self.assert_refused(
            self.payload(
                [
                    {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk, self.lesson_b.pk]},
                    {"folder": self.section_one.pk, "lessons": [self.lesson_c.pk]},
                ]
            )
        )

    def test_broken_json_is_a_400_with_a_sentence(self):
        response = self.client.post(self.url, data="{not json", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("not readable", response.json()["message"])

    def test_an_empty_body_is_a_400_not_a_traceback(self):
        response = self.client.post(self.url, data="", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_a_lesson_id_that_is_not_a_number_is_refused(self):
        response = self.post(
            self.payload(
                [
                    {"folder": self.section_one.pk, "lessons": [self.lesson_a.pk, self.lesson_b.pk]},
                    {"folder": self.section_two.pk, "lessons": ["one", self.lesson_c.pk]},
                ]
            )
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("not a number", response.json()["message"])

    def test_a_boolean_is_not_read_as_an_id(self):
        # `True` is an int in Python; treating it as lesson 1 would move a class
        # nobody asked to move.
        response = self.post(
            self.payload(
                [
                    {"folder": self.section_one.pk, "lessons": [True, self.lesson_a.pk, self.lesson_b.pk]},
                    {"folder": self.section_two.pk, "lessons": [self.lesson_c.pk]},
                ]
            )
        )
        self.assertEqual(response.status_code, 400)


class OutlineOrderUnitTests(OutlineFixture):
    def test_the_revision_is_stable_until_the_order_changes(self):
        first = revision_of(build_outline(self.course))
        self.assertEqual(first, revision_of(build_outline(self.course)))

        self.lesson_a.position = 1
        self.lesson_b.position = 0
        self.lesson_a.save(update_fields=["position"])
        self.lesson_b.save(update_fields=["position"])
        self.assertNotEqual(first, revision_of(build_outline(self.course)))

    def test_apply_order_refuses_a_payload_that_is_not_an_object(self):
        with self.assertRaises(OutlineError) as caught:
            apply_order(self.course, ["not", "a", "dict"])
        self.assertEqual(caught.exception.status, 400)
