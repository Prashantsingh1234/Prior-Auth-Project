"""
Locust load testing configuration for the PA Review Platform.

Usage:
    # Basic run (headless):
    locust -f app/tests/load/locustfile.py \
        --host=http://localhost:8000 \
        --users=50 --spawn-rate=5 \
        --run-time=5m --headless

    # With web UI:
    locust -f app/tests/load/locustfile.py --host=http://localhost:8000

    # Specific user classes:
    locust -f app/tests/load/locustfile.py \
        --host=http://localhost:8000 \
        --users=100 --spawn-rate=10 \
        ProviderUser ReviewerUser

User Classes:
    HealthCheckUser  — K8s probe simulation (low weight, constant rate)
    ReviewerUser     — Clinical reviewer session (main read/write workload)
    ProviderUser     — PA submission and clarification responses
    AdminUser        — Metrics + assignment (low volume, admin ops)

Performance Targets:
    P50 latency: < 200ms  (case list, health)
    P95 latency: < 800ms  (case detail, approve/deny)
    P99 latency: < 2000ms (PA submission with validation)
    Error rate: < 0.1%
    Throughput: 200 RPS steady state
"""

from __future__ import annotations

import json
import os
import random
import string
import uuid
from datetime import UTC, datetime

from locust import HttpUser, between, constant, events, task
from locust.runners import MasterRunner


# ---------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------

API_PREFIX = "/api/v1"

# Auth tokens (set via environment or use placeholder for rate-limit testing)
REVIEWER_TOKEN = os.getenv("LOAD_TEST_REVIEWER_TOKEN", "reviewer-test-token")
ADMIN_TOKEN = os.getenv("LOAD_TEST_ADMIN_TOKEN", "admin-test-token")
PROVIDER_TOKEN = os.getenv("LOAD_TEST_PROVIDER_TOKEN", "provider-test-token")

# Case IDs seeded at test start — populated by provider submissions
_active_case_ids: list[str] = []
_pending_clarification_case_ids: list[str] = []


def _reviewer_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {REVIEWER_TOKEN}",
        "Content-Type": "application/json",
    }


def _admin_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
    }


def _provider_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {PROVIDER_TOKEN}",
        "Content-Type": "application/json",
    }


def _random_npi() -> str:
    return "".join([str(random.randint(0, 9)) for _ in range(10)])


def _random_member_id() -> str:
    return f"MBR-{random.randint(100000, 999999)}"


def _pa_request_payload() -> dict:
    cpt_options = [["95249"], ["70553"], ["27447"], ["93454"], ["E0601"], ["99213"]]
    icd_options = [["E11.9"], ["G35"], ["M17.11"], ["I25.10"], ["G47.33"], ["M05.79"]]

    return {
        "patient": {
            "first_name": f"Patient{random.randint(1000, 9999)}",
            "last_name": f"Test{random.randint(100, 999)}",
            "date_of_birth": "1975-06-15",
            "gender": random.choice(["male", "female"]),
            "member_id": _random_member_id(),
            "group_number": f"GRP-{random.randint(1000, 9999)}",
            "insurance_plan_name": random.choice([
                "BlueCross PPO", "United PPO", "Aetna HMO", "Cigna PPO"
            ]),
            "insurance_plan_id": f"PLN-{random.randint(100, 999)}",
        },
        "provider": {
            "npi": _random_npi(),
            "first_name": f"Dr{random.randint(10, 99)}",
            "last_name": f"Provider{random.randint(100, 999)}",
            "specialty": random.choice([
                "Internal Medicine", "Cardiology", "Neurology", "Orthopedics"
            ]),
            "organization_name": f"Medical Center {random.randint(1, 50)}",
            "phone": "555-000-0000",
            "fax": "555-000-0001",
        },
        "service_type": random.choice(["IMAGING", "PROCEDURE", "MEDICATION", "SPECIALTY_REFERRAL"]),
        "cpt_codes": random.choice(cpt_options),
        "icd_codes": random.choice(icd_options),
        "priority": random.choices(
            ["ROUTINE", "URGENT", "EMERGENT"],
            weights=[70, 25, 5],
        )[0],
        "requested_service_description": "Load test PA request for performance benchmarking.",
        "clinical_notes": (
            "Patient requires this service based on documented clinical evidence. "
            "All required documentation has been submitted. "
            "This request is generated as part of load testing."
        ),
        "source_channel": "load_test",
    }


# ---------------------------------------------------------------
# User classes
# ---------------------------------------------------------------

class HealthCheckUser(HttpUser):
    """
    Simulates K8s liveness/readiness probes and monitoring polling.
    Very high frequency, very low payload. Represents ~5% of total load.
    """
    wait_time = constant(5)
    weight = 2

    @task(2)
    def liveness_probe(self) -> None:
        with self.client.get(
            f"{API_PREFIX}/health/live",
            catch_response=True,
            name="/health/live",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Liveness probe: {resp.status_code}")

    @task(1)
    def readiness_probe(self) -> None:
        with self.client.get(
            f"{API_PREFIX}/health/ready",
            catch_response=True,
            name="/health/ready",
        ) as resp:
            if resp.status_code in (200, 503):
                resp.success()
            else:
                resp.failure(f"Readiness probe: {resp.status_code}")

    @task(1)
    def full_health(self) -> None:
        with self.client.get(
            f"{API_PREFIX}/health",
            catch_response=True,
            name="/health",
        ) as resp:
            if resp.status_code in (200, 207):
                resp.success()
            else:
                resp.failure(f"Health check: {resp.status_code}")


class ReviewerUser(HttpUser):
    """
    Simulates a clinical reviewer working through the PA queue.
    Mix of list, detail, and decision operations.
    Represents ~50% of production load.
    """
    wait_time = between(2, 8)
    weight = 20

    def on_start(self) -> None:
        """Authenticate and load initial case queue."""
        self.headers = _reviewer_headers()
        # Verify auth works
        self.client.get(f"{API_PREFIX}/health/live")

    @task(5)
    def list_cases(self) -> None:
        """Browse the reviewer queue — most common action."""
        status = random.choice(["UNDER_REVIEW", "ESCALATED", "SUBMITTED"])
        with self.client.get(
            f"{API_PREFIX}/cases?status={status}&limit=20",
            headers=self.headers,
            catch_response=True,
            name="/cases [list]",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Authentication failed")
            else:
                resp.success()  # Other errors are acceptable in load test context

    @task(4)
    def list_cases_paginated(self) -> None:
        """Simulate paging through results."""
        page = random.randint(1, 5)
        with self.client.get(
            f"{API_PREFIX}/cases?page={page}&page_size=10",
            headers=self.headers,
            catch_response=True,
            name="/cases [paginated]",
        ) as resp:
            if resp.status_code in (200, 401):
                resp.success()

    @task(3)
    def get_case_detail(self) -> None:
        """View a specific case — triggered when reviewer opens a case."""
        case_id = random.choice(_active_case_ids) if _active_case_ids else str(uuid.uuid4())
        with self.client.get(
            f"{API_PREFIX}/cases/{case_id}",
            headers=self.headers,
            catch_response=True,
            name="/cases/{case_id} [detail]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Authentication failed")

    @task(2)
    def approve_case(self) -> None:
        """Reviewer approves a PA case."""
        case_id = random.choice(_active_case_ids) if _active_case_ids else str(uuid.uuid4())
        with self.client.post(
            f"{API_PREFIX}/review/{case_id}/approve",
            json={"rationale": "Patient meets all clinical criteria per current policy guidelines."},
            headers=self.headers,
            catch_response=True,
            name="/review/{id}/approve",
        ) as resp:
            if resp.status_code in (200, 404, 409):
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Authentication failed")

    @task(1)
    def deny_case(self) -> None:
        """Reviewer denies a PA case."""
        case_id = random.choice(_active_case_ids) if _active_case_ids else str(uuid.uuid4())
        with self.client.post(
            f"{API_PREFIX}/review/{case_id}/deny",
            json={
                "rationale": "Documentation does not meet medical necessity criteria per policy.",
                "denial_reason_code": "NOT_MEDICALLY_NECESSARY",
            },
            headers=self.headers,
            catch_response=True,
            name="/review/{id}/deny",
        ) as resp:
            if resp.status_code in (200, 404, 409):
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Authentication failed")

    @task(1)
    def pend_case(self) -> None:
        """Reviewer pends a case for additional information."""
        case_id = random.choice(_active_case_ids) if _active_case_ids else str(uuid.uuid4())
        with self.client.post(
            f"{API_PREFIX}/review/{case_id}/pend",
            json={
                "rationale": "Awaiting additional lab documentation from treating physician.",
                "pending_reason": "Additional clinical documentation required",
            },
            headers=self.headers,
            catch_response=True,
            name="/review/{id}/pend",
        ) as resp:
            if resp.status_code in (200, 404, 409):
                resp.success()

    @task(1)
    def add_note(self) -> None:
        """Reviewer adds a note to a case."""
        case_id = random.choice(_active_case_ids) if _active_case_ids else str(uuid.uuid4())
        with self.client.post(
            f"{API_PREFIX}/review/{case_id}/notes",
            json={"note": "Reviewed additional clinical documentation. Proceeding with decision."},
            headers=self.headers,
            catch_response=True,
            name="/review/{id}/notes",
        ) as resp:
            if resp.status_code in (200, 201, 404):
                resp.success()

    @task(1)
    def get_clarifications(self) -> None:
        """Reviewer checks clarification status on a case."""
        case_id = (
            random.choice(_pending_clarification_case_ids)
            if _pending_clarification_case_ids
            else str(uuid.uuid4())
        )
        with self.client.get(
            f"{API_PREFIX}/clarification/{case_id}",
            headers=self.headers,
            catch_response=True,
            name="/clarification/{id} [list]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()


class ProviderUser(HttpUser):
    """
    Simulates a healthcare provider submitting PA requests and responding to clarifications.
    Represents ~40% of production load (many providers, less frequent actions each).
    """
    wait_time = between(5, 30)
    weight = 15

    def on_start(self) -> None:
        self.headers = _provider_headers()
        self.submitted_cases: list[str] = []

    @task(3)
    def submit_pa_request(self) -> None:
        """Provider submits a new PA request."""
        with self.client.post(
            f"{API_PREFIX}/pa-requests",
            json=_pa_request_payload(),
            headers=self.headers,
            catch_response=True,
            name="/pa-requests [submit]",
        ) as resp:
            if resp.status_code == 202:
                try:
                    data = resp.json()
                    case_id = data.get("data", {}).get("case_id")
                    if case_id:
                        _active_case_ids.append(case_id)
                        self.submitted_cases.append(case_id)
                        if len(_active_case_ids) > 500:
                            _active_case_ids.pop(0)
                except (json.JSONDecodeError, KeyError):
                    pass
                resp.success()
            elif resp.status_code in (401, 409, 422):
                resp.success()  # Expected failures in load test
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def check_case_status(self) -> None:
        """Provider polls their case status."""
        case_id = (
            random.choice(self.submitted_cases)
            if self.submitted_cases
            else str(uuid.uuid4())
        )
        with self.client.get(
            f"{API_PREFIX}/cases/{case_id}",
            headers=self.headers,
            catch_response=True,
            name="/cases/{case_id} [provider view]",
        ) as resp:
            if resp.status_code in (200, 403, 404):
                resp.success()

    @task(1)
    def respond_to_clarification(self) -> None:
        """Provider responds to a clarification request."""
        case_id = (
            random.choice(_pending_clarification_case_ids)
            if _pending_clarification_case_ids
            else str(uuid.uuid4())
        )
        with self.client.post(
            f"{API_PREFIX}/clarification/{case_id}/respond",
            json={
                "clarification_id": str(uuid.uuid4()),
                "response": (
                    "The patient has been diagnosed with the condition for over 3 years. "
                    "HbA1c is 9.2%. Currently on insulin therapy as documented in attached records. "
                    "All requested documentation has been provided."
                ),
            },
            headers=self.headers,
            catch_response=True,
            name="/clarification/{id}/respond",
        ) as resp:
            if resp.status_code in (200, 404, 409, 422):
                resp.success()


class AdminUser(HttpUser):
    """
    Simulates admin operations: metrics monitoring, reviewer assignments.
    Low volume, high impact. Represents ~5% of production load.
    """
    wait_time = between(10, 60)
    weight = 3

    def on_start(self) -> None:
        self.headers = _admin_headers()

    @task(3)
    def get_business_metrics(self) -> None:
        """Admin monitors business KPI dashboard."""
        with self.client.get(
            f"{API_PREFIX}/metrics",
            headers=self.headers,
            catch_response=True,
            name="/metrics [business]",
        ) as resp:
            if resp.status_code in (200, 401, 403):
                resp.success()

    @task(1)
    def get_prometheus_metrics(self) -> None:
        """Admin scrapes Prometheus metrics."""
        with self.client.get(
            f"{API_PREFIX}/metrics/prometheus",
            headers=self.headers,
            catch_response=True,
            name="/metrics/prometheus",
        ) as resp:
            if resp.status_code in (200, 401, 403, 503):
                resp.success()

    @task(2)
    def assign_reviewer(self) -> None:
        """Admin assigns cases to reviewers."""
        case_id = random.choice(_active_case_ids) if _active_case_ids else str(uuid.uuid4())
        reviewer_ids = [
            "reviewer-uuid-001",
            "reviewer-uuid-002",
            "reviewer-uuid-003",
        ]
        with self.client.post(
            f"{API_PREFIX}/review/{case_id}/assign",
            json={"reviewer_id": random.choice(reviewer_ids)},
            headers=self.headers,
            catch_response=True,
            name="/review/{id}/assign",
        ) as resp:
            if resp.status_code in (200, 404, 409):
                resp.success()


# ---------------------------------------------------------------
# Custom load shape
# ---------------------------------------------------------------

class SpikeLoadShape:
    """
    Custom load shape for spike testing.
    Ramps up to peak, holds steady, then spikes, then recovers.

    Register in locust.conf or as --shape-class argument:
        locust -f locustfile.py --shape-class=SpikeLoadShape
    """
    stages = [
        {"duration": 60,  "users": 10,  "spawn_rate": 2},    # Warm-up
        {"duration": 120, "users": 50,  "spawn_rate": 5},    # Normal load
        {"duration": 180, "users": 100, "spawn_rate": 10},   # Peak load
        {"duration": 60,  "users": 200, "spawn_rate": 50},   # Spike
        {"duration": 120, "users": 100, "spawn_rate": 10},   # Recovery
        {"duration": 60,  "users": 10,  "spawn_rate": 5},    # Wind-down
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
            run_time -= stage["duration"]
        return None


# ---------------------------------------------------------------
# Event hooks for test lifecycle management
# ---------------------------------------------------------------

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Pre-populate test data at the start of the load test."""
    if not isinstance(environment.runner, MasterRunner):
        # Seed some known case IDs for read operations
        for i in range(20):
            _active_case_ids.append(str(uuid.uuid4()))


@events.request.add_listener
def on_request(
    request_type,
    name,
    response_time,
    response_length,
    exception,
    context,
    **kwargs,
):
    """Log slow requests for performance investigation."""
    if response_time > 2000:  # > 2 seconds
        print(
            f"SLOW REQUEST: {request_type} {name} "
            f"took {response_time:.0f}ms"
        )
