"""Tests for the centralised error handling."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from routers import slices as slices_router


@pytest.fixture
def client() -> TestClient:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


class TestErrorEnvelope:
    def test_a_404_carries_code_and_request_id(self, client: TestClient) -> None:
        response = client.get("/api/slices/does-not-exist")
        body = response.json()
        assert response.status_code == 404
        assert body["code"] == "not_found"
        assert body["request_id"]

    def test_a_validation_error_carries_code_and_request_id(
        self, client: TestClient
    ) -> None:
        response = client.post("/api/slices/provision", json={"intent": "   "})
        body = response.json()
        assert response.status_code == 422
        assert body["code"] == "validation_error"
        assert body["request_id"]

    def test_request_id_matches_the_response_header(self, client: TestClient) -> None:
        response = client.get("/api/slices/does-not-exist")
        assert response.json()["request_id"] == response.headers["X-Request-ID"]

    def test_an_unhandled_exception_never_leaks_internals(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def explode():
            raise RuntimeError("a secret internal detail")

        monkeypatch.setattr(slices_router.slice_registry, "get_all_slices", explode)

        response = client.get("/api/slices")
        body = response.json()

        assert response.status_code == 500
        assert body["code"] == "internal_error"
        assert body["request_id"]
        assert "secret internal detail" not in response.text
        assert "RuntimeError" not in response.text
        assert "Traceback" not in response.text

    def test_the_service_recovers_after_a_single_failure(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def explode():
            raise RuntimeError("boom")

        monkeypatch.setattr(slices_router.slice_registry, "get_all_slices", explode)
        assert client.get("/api/slices").status_code == 500

        monkeypatch.undo()
        assert client.get("/api/slices").status_code == 200
