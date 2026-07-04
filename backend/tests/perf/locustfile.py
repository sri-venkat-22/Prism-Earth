"""Load test for the Prism Earth REST API (SRS §30.3 Table 7, §7.1).

Models the read-heavy production traffic mix — public metadata discovery plus the
authenticated data endpoints — so latency and throughput can be measured against
the §7.1 performance targets. This is an operational tool, not part of the CI
unit/integration gate.

Usage (against a running instance)::

    pip install locust
    locust -f backend/tests/perf/locustfile.py --host http://localhost:8000

Set ``PRISM_BEARER_TOKEN`` when the target has authentication enabled (§13.20);
without it the /fetch and /ask calls will receive 401s (still a useful signal for
the gateway path).
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, task

# A spread of coordinates inside the Telangana pilot region (SRS §24).
_POINTS = [
    (17.385, 78.486),  # Hyderabad
    (17.240, 78.430),  # Rajendranagar
    (18.100, 79.020),  # near Karimnagar
    (16.510, 80.630),  # Vijayawada fringe
]
_PRESETS = ["terrain", "climate", "flood_risk", "solar_suitability"]
_QUESTIONS = [
    "Is this area suitable for solar farm development?",
    "What is the flood risk at this location?",
    "Describe the terrain and elevation here.",
]


def _auth_headers() -> dict[str, str]:
    token = os.environ.get("PRISM_BEARER_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


class PrismUser(HttpUser):
    """A synthetic API client exercising the core flows."""

    wait_time = between(0.5, 2.5)

    @task(5)
    def list_fields(self) -> None:
        self.client.get("/api/v1/meta/fields", name="/meta/fields")

    @task(3)
    def list_presets(self) -> None:
        self.client.get("/api/v1/meta/presets", name="/meta/presets")

    @task(2)
    def health(self) -> None:
        self.client.get("/api/v1/health", name="/health")

    @task(6)
    def fetch(self) -> None:
        lat, lng = random.choice(_POINTS)  # noqa: S311 - non-cryptographic test spread
        self.client.post(
            "/api/v1/fetch",
            json={"lat": lat, "lng": lng, "preset": random.choice(_PRESETS)},  # noqa: S311
            headers=_auth_headers(),
            name="/fetch",
        )

    @task(2)
    def ask(self) -> None:
        lat, lng = random.choice(_POINTS)  # noqa: S311
        self.client.post(
            "/api/v1/ask",
            json={"lat": lat, "lng": lng, "question": random.choice(_QUESTIONS)},  # noqa: S311
            headers=_auth_headers(),
            name="/ask",
        )
