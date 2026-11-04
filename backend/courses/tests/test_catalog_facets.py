"""The catalogue's filters: what each count means, and what it refuses to mean.

The panel is only honest if a count answers the question a learner is about to
ask: *if I tick this, how many batches will I see?* That is a count with the
other groups applied and this one left out — so ticking Physics must not erase
Biology from the list of subjects.

These tests pin that rule, plus the smaller ones around it: blanks are not a
facet value, an unpublished batch is in no count, and repeated parameters are
how a checkbox group travels.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import Course

User = get_user_model()


class FacetData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="provider", email="p@example.com", password="TestPass123!", is_staff=True
        )
        cls.owner.profile.role = Role.SUB_ADMIN
        cls.owner.profile.save()

        def batch(slug, title, exam="", subject="Physics", level="", published=True, **extra):
            return Course.objects.create(
                title=title,
                slug=slug,
                exam=exam,
                subject=subject,
                level=level,
                description=f"{title} description",
                is_published=published,
                owner=cls.owner,
                **extra,
            )

        cls.jee_12 = batch("jee-12", "JEE Class 12", exam="JEE", level="Class 12")
        cls.jee_drop = batch(
            "jee-drop", "JEE Dropper", exam="JEE", level="Dropper",
            pricing_mode=Course.PricingMode.PAID, price=Decimal("4999.00"),
        )
        cls.neet_12 = batch(
            "neet-12", "NEET Class 12", exam="NEET", subject="Biology", level="Class 12"
        )
        # No exam, no level: listed, but never a facet value.
        cls.untagged = batch("untagged", "Physics Refresher", subject="Physics")
        cls.hidden = batch("hidden", "Draft JEE Batch", exam="JEE", published=False)

    def setUp(self):
        self.client = APIClient()

    def facets(self, query=""):
        response = self.client.get(f"/api/courses/facets/{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def counts(self, payload, group):
        return {row["value"]: row["count"] for row in payload["facets"][group]}


class FacetShapeTests(FacetData):
    def test_facets_are_public_and_counted_per_group(self):
        payload = self.facets()
        self.assertEqual(payload["count"], 4, "the draft batch is in no count")
        self.assertEqual(self.counts(payload, "exam"), {"JEE": 2, "NEET": 1})
        self.assertEqual(self.counts(payload, "level"), {"Class 12": 2, "Dropper": 1})
        self.assertEqual(
            self.counts(payload, "subject"), {"Physics": 3, "Biology": 1}
        )
        self.assertEqual(self.counts(payload, "pricing_mode"), {"free": 3, "paid": 1})

    def test_a_batch_with_no_exam_is_listed_but_never_a_value(self):
        payload = self.facets()
        self.assertNotIn("", self.counts(payload, "exam"))
        listed = self.client.get("/api/courses/").json()["results"]
        self.assertIn("untagged", [row["slug"] for row in listed], "still in the catalogue")

    def test_an_unknown_value_empties_the_result_but_not_the_other_groups(self):
        payload = self.facets("?exam=Nonsense")
        self.assertEqual(payload["count"], 0)
        self.assertEqual(self.counts(payload, "exam"), {"JEE": 2, "NEET": 1}, "its own group keeps its counts")
        self.assertEqual(self.counts(payload, "subject"), {}, "nothing matches, so no alternatives")


class FacetIsolationTests(FacetData):
    def test_a_ticked_facet_does_not_erase_its_siblings(self):
        payload = self.facets("?subject=Physics")
        self.assertEqual(payload["count"], 3, "both Physics batches and the untagged one")
        self.assertEqual(
            self.counts(payload, "subject"),
            {"Physics": 3, "Biology": 1},
            "Physics is ticked, Biology is still offered",
        )

    def test_the_other_groups_narrow_to_the_current_selection(self):
        payload = self.facets("?subject=Physics")
        self.assertEqual(
            self.counts(payload, "exam"),
            {"JEE": 2},
            "only exams that actually have a Physics batch",
        )
        self.assertEqual(self.counts(payload, "level"), {"Class 12": 1, "Dropper": 1})

    def test_price_is_counted_without_its_own_filter(self):
        payload = self.facets("?pricing_mode=paid")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(self.counts(payload, "pricing_mode"), {"free": 3, "paid": 1})


class SelectionTests(FacetData):
    def test_repeated_parameters_are_an_or(self):
        payload = self.client.get("/api/courses/?exam=JEE&exam=NEET").json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(
            sorted(row["slug"] for row in payload["results"]),
            ["jee-12", "jee-drop", "neet-12"],
        )

    def test_facets_may_be_combined_with_search(self):
        payload = self.facets("?search=NEET")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(self.counts(payload, "exam"), {"NEET": 1})

    def test_search_matches_the_exam_name_itself(self):
        payload = self.client.get("/api/courses/?search=Dropper").json()
        self.assertEqual([row["slug"] for row in payload["results"]], ["jee-drop"])

    def test_facets_follow_mine(self):
        self.client.force_authenticate(self.owner)
        payload = self.facets("?mine=1")
        self.assertEqual(payload["count"], 0, "the provider enrolled in nothing")

    def test_the_facet_route_is_not_mistaken_for_a_batch_id(self):
        response = self.client.get("/api/courses/999999/")
        self.assertEqual(response.status_code, 404)
