from django.test import SimpleTestCase
from django.urls import reverse


class FoundationEndpointTests(SimpleTestCase):
    def test_health_endpoint_returns_minimal_json(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Content-Type"], "application/json")

    def test_health_endpoint_rejects_non_get_methods(self):
        response = self.client.post(reverse("healthz"))

        self.assertEqual(response.status_code, 405)

    def test_api_root_is_reachable(self):
        response = self.client.get("/api/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("courses", response.json())
        self.assertIn("lessons", response.json())
