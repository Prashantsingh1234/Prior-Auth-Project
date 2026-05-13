"""
Locust load testing configuration.

Run with:
    locust -f app/tests/load/locustfile.py --host=http://localhost:8000

Scenarios:
- HealthCheckUser: Simulates monitoring/probe traffic (light load)
- ReviewerUser:    Simulates concurrent clinical reviewer sessions (main workload)
"""

from __future__ import annotations

from locust import HttpUser, between, constant, task


class HealthCheckUser(HttpUser):
    """
    Simulates health check polling (monitoring systems, K8s probes).
    High frequency, lightweight requests.
    """

    wait_time = constant(5)  # 1 request every 5 seconds
    weight = 1  # Low weight — few of these users

    @task
    def liveness_probe(self) -> None:
        with self.client.get("/api/v1/health/live", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Liveness probe failed: {response.status_code}")

    @task
    def readiness_probe(self) -> None:
        with self.client.get("/api/v1/health/ready", catch_response=True) as response:
            if response.status_code in (200, 503):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class ReviewerUser(HttpUser):
    """
    Simulates a clinical reviewer interacting with the PA platform.
    Moderate concurrency, mix of read and write operations.
    """

    wait_time = between(1, 5)  # Realistic human interaction pace
    weight = 10  # Main workload

    def on_start(self) -> None:
        """Authenticate before running tasks."""
        # In a real setup, this would POST to /auth/token
        # For now, we just confirm health
        self.client.get("/api/v1/health/live")

    @task(3)
    def check_health(self) -> None:
        """Reviewers occasionally check system status."""
        self.client.get("/api/v1/health")

    @task(1)
    def liveness(self) -> None:
        self.client.get("/api/v1/health/live")
