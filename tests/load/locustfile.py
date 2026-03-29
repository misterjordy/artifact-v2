"""Load test script using Locust — 50 concurrent users, p95 < 2s target."""

import random
import string

from locust import HttpUser, between, task


class ArtifactUser(HttpUser):
    """Simulates a typical artiFACT user browsing, searching, and exporting."""

    wait_time = between(1, 3)

    def on_start(self) -> None:
        """Authenticate and store CSRF token."""
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        if resp.status_code == 200:
            data = resp.json()
            self.csrf_token = data.get("csrf_token", "")
        else:
            self.csrf_token = ""

    @task(5)
    def browse_tree(self) -> None:
        """Browse the taxonomy tree."""
        self.client.get("/api/v1/nodes")

    @task(3)
    def browse_facts(self) -> None:
        """Browse facts for a node."""
        self.client.get("/api/v1/facts?limit=50")

    @task(2)
    def search(self) -> None:
        """Search for a random term."""
        term = "".join(random.choices(string.ascii_lowercase, k=4))
        self.client.get(f"/api/v1/search?q={term}")

    @task(1)
    def queue_check(self) -> None:
        """Check queue counts."""
        self.client.get("/api/v1/queue/counts")

    @task(1)
    def health_check(self) -> None:
        """Health check."""
        self.client.get("/api/v1/health")
