"""The page size a screen asks for is the page size it gets.

Every list endpoint is read by a rail or a grid that shows a fixed number of
rows: four lessons on the home page, nine batches in the catalogue, the whole
paper list on the tests page. DRF's stock pagination ignores ``page_size``, so
those screens silently received the default 50 rows and rendered everything the
database held. These tests pin the behaviour they rely on.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model

from courses.models import Course


class PageSizeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="pager_owner", password="pw-for-tests-1234"
        )
        for index in range(7):
            Course.objects.create(
                title=f"Batch {index}",
                slug=f"batch-{index}",
                owner=cls.owner,
                pricing_mode=Course.PricingMode.FREE,
                is_published=True,
            )

    def setUp(self):
        self.client = APIClient()

    def test_page_size_is_honoured(self):
        response = self.client.get("/api/courses/", {"page_size": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 7)
        self.assertEqual(len(response.data["results"]), 3)

    def test_default_page_size_applies_without_the_parameter(self):
        response = self.client.get("/api/courses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 7)  # fewer than the default

    def test_page_size_is_capped(self):
        response = self.client.get("/api/courses/", {"page_size": 5000})
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.data["results"]), 100)

    def test_second_page_continues_the_list(self):
        first = self.client.get("/api/courses/", {"page_size": 3, "page": 1})
        second = self.client.get("/api/courses/", {"page_size": 3, "page": 2})
        self.assertEqual(len(first.data["results"]), 3)
        self.assertEqual(len(second.data["results"]), 3)
        self.assertNotEqual(first.data["results"][0]["id"], second.data["results"][0]["id"])
