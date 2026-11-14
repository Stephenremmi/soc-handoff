from unittest import TestCase

import httpx

from soc_handoff.errors import TrackerUnavailable
from soc_handoff.integrations.tracker import TrackerClient


class TrackerConfirmationTest(TestCase):
    sample_run = {
        "_id": "demo-run",
        "title": "Review synthetic sign-in",
        "alert_id": "SOC-1042",
        "evidence": "IDP-9031",
    }

    def test_create_rejects_unconfirmed_ticket(self):
        cases = [
            {},
            {"id": "TKT-0001", "run_id": "different-run", "status": "open"},
            {"id": "TKT-0001", "run_id": "demo-run", "status": "closed"},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                transport = httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
                with httpx.Client(base_url="http://tracker.test", transport=transport) as client:
                    with self.assertRaises(TrackerUnavailable):
                        TrackerClient(client, "test-token").create(self.sample_run)

    def test_rollback_requires_same_ticket_and_closed_status(self):
        payload = {"id": "TKT-0001", "run_id": "demo-run", "status": "open"}
        transport = httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        with httpx.Client(base_url="http://tracker.test", transport=transport) as client:
            tracker = TrackerClient(client, "test-token")
            with self.assertRaises(TrackerUnavailable):
                tracker.close("demo-run", "TKT-0001")
            payload["status"] = "closed"
            with self.assertRaises(TrackerUnavailable):
                tracker.close("demo-run", "TKT-0002")
            tracker.close("demo-run", "TKT-0001")
