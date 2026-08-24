"""Tests for the request body size guard.

MaxBodySizeMiddleware reads its limit once, at construction time, the same
pattern RateLimitMiddleware already uses elsewhere in this file - config is
static for the process lifetime, not re-read per request. That makes it
untestable by monkeypatching `settings` after `main.app` has already been
built, so these tests mount the middleware directly on a minimal, isolated
app instead of going through the real one.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.middleware import MaxBodySizeMiddleware


def make_app(max_bytes: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=max_bytes)

    @app.post("/echo")
    async def echo(payload: dict) -> dict:
        return payload

    return app


class TestBodySizeLimit:
    def test_a_body_within_the_limit_is_accepted(self) -> None:
        with TestClient(make_app(max_bytes=1000)) as client:
            response = client.post("/echo", json={"value": "short"})
            assert response.status_code == 200

    def test_an_oversized_body_is_rejected_with_413(self) -> None:
        with TestClient(make_app(max_bytes=100)) as client:
            response = client.post("/echo", json={"value": "x" * 500})
            assert response.status_code == 413
            body = response.json()
            assert body["code"] == "payload_too_large"
            assert body["request_id"]

    def test_the_rejection_never_reaches_the_route_handler(self) -> None:
        # Proven indirectly: if the route ran, it would echo the oversized
        # payload back as a 200. Getting 413 means the route never executed.
        with TestClient(make_app(max_bytes=50)) as client:
            response = client.post("/echo", json={"value": "x" * 500})
            assert response.status_code == 413

    def test_a_limit_of_zero_disables_the_check(self) -> None:
        with TestClient(make_app(max_bytes=0)) as client:
            response = client.post("/echo", json={"value": "x" * 5000})
            assert response.status_code == 200

    def test_a_request_without_a_body_is_unaffected(self) -> None:
        app = FastAPI()
        app.add_middleware(MaxBodySizeMiddleware, max_bytes=10)

        @app.get("/ping")
        async def ping() -> dict:
            return {"ok": True}

        with TestClient(app) as client:
            assert client.get("/ping").status_code == 200


class TestAgainstTheRealApp:
    def test_the_configured_default_easily_covers_a_maximal_intent(self) -> None:
        # No isolated app here: exercises the real HELIX app with its actual
        # configured default against the largest legitimate request the
        # intent field itself allows, end to end.
        from main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/slices/provision", json={"intent": "iot slice " + "x" * 1900}
            )
            assert response.status_code != 413
