"""Tests for the HTTP middleware stack."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


class TestSecurityHeaders:
    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "no-referrer"),
        ],
    )
    def test_present_on_a_successful_response(
        self, client: TestClient, header: str, expected: str
    ) -> None:
        response = client.get("/health")
        assert response.headers[header] == expected

    def test_present_on_a_404(self, client: TestClient) -> None:
        response = client.get("/api/slices/does-not-exist")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_present_on_a_validation_error(self, client: TestClient) -> None:
        response = client.post("/api/slices/provision", json={"intent": ""})
        assert response.headers.get("X-Frame-Options") == "DENY"


class TestRequestContext:
    def test_every_response_carries_a_request_id(self, client: TestClient) -> None:
        assert client.get("/health").headers.get("X-Request-ID")

    def test_an_inbound_request_id_is_echoed_back(self, client: TestClient) -> None:
        response = client.get("/health", headers={"X-Request-ID": "trace-42"})
        assert response.headers["X-Request-ID"] == "trace-42"

    def test_each_request_gets_a_distinct_id_by_default(self, client: TestClient) -> None:
        first = client.get("/health").headers["X-Request-ID"]
        second = client.get("/health").headers["X-Request-ID"]
        assert first != second

    def test_response_time_header_is_present_and_numeric(self, client: TestClient) -> None:
        value = client.get("/health").headers["X-Response-Time-Ms"]
        assert float(value) >= 0
