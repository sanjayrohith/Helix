"""Tests for API-key authentication."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.auth import Principal, parse_api_keys, redact
from main import app


class TestKeyParsing:
    def test_parses_key_scope_and_label(self) -> None:
        keys = parse_api_keys("sk_abc:write:ops-team")
        assert keys["sk_abc"] == Principal(actor="ops-team", scope="write")

    def test_label_defaults_to_a_redacted_form_of_the_key(self) -> None:
        keys = parse_api_keys("sk_abc:read")
        assert keys["sk_abc"].actor == redact("sk_abc")
        assert "sk_abc" not in keys["sk_abc"].actor

    def test_multiple_entries_are_comma_separated(self) -> None:
        keys = parse_api_keys("sk_a:write:ops, sk_b:read:viewer")
        assert set(keys) == {"sk_a", "sk_b"}

    def test_an_empty_string_yields_no_keys(self) -> None:
        assert parse_api_keys("") == {}
        assert parse_api_keys("   ") == {}

    @pytest.mark.parametrize(
        "entry",
        [
            "sk_abc",  # missing scope
            "sk_abc:write:ops:extra",  # too many fields
            "sk_abc:admin",  # unknown scope
            ":write:ops",  # empty key
        ],
    )
    def test_malformed_entries_are_skipped_not_raised(self, entry: str) -> None:
        # Must never raise: one typo in the environment should not take the
        # whole API down.
        assert parse_api_keys(entry) == {}

    def test_one_bad_entry_does_not_drop_the_good_ones(self) -> None:
        keys = parse_api_keys("sk_good:write:ops, malformed, sk_also_good:read")
        assert set(keys) == {"sk_good", "sk_also_good"}


class TestScopeSatisfaction:
    def test_write_satisfies_read(self) -> None:
        assert Principal(actor="x", scope="write").satisfies("read")

    def test_write_satisfies_write(self) -> None:
        assert Principal(actor="x", scope="write").satisfies("write")

    def test_read_satisfies_read(self) -> None:
        assert Principal(actor="x", scope="read").satisfies("read")

    def test_read_does_not_satisfy_write(self) -> None:
        assert not Principal(actor="x", scope="read").satisfies("write")


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client against an app with auth enabled and two keys configured."""
    monkeypatch.setattr(
        "core.config.settings.api_keys_raw",
        "sk_write_key:write:ops-team,sk_read_key:read:dashboard",
    )
    with TestClient(app) as test_client:
        yield test_client


class TestEnforcement:
    def test_no_key_is_rejected_with_401(self, auth_client: TestClient) -> None:
        response = auth_client.get("/api/slices")
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_an_unrecognised_key_is_rejected_with_401(self, auth_client: TestClient) -> None:
        response = auth_client.get("/api/slices", headers={"X-API-Key": "not-a-real-key"})
        assert response.status_code == 401

    def test_a_read_key_can_read(self, auth_client: TestClient) -> None:
        response = auth_client.get("/api/slices", headers={"X-API-Key": "sk_read_key"})
        assert response.status_code == 200

    def test_a_read_key_cannot_write(self, auth_client: TestClient) -> None:
        response = auth_client.post(
            "/api/slices/provision",
            json={"intent": "iot slice with 5 Mbps in Pune"},
            headers={"X-API-Key": "sk_read_key"},
        )
        assert response.status_code == 403

    def test_a_write_key_can_both_read_and_write(self, auth_client: TestClient) -> None:
        headers = {"Authorization": "Bearer sk_write_key"}
        provisioned = auth_client.post(
            "/api/slices/provision",
            json={"intent": "iot slice with 5 Mbps in Pune"},
            headers=headers,
        )
        assert provisioned.status_code == 200
        assert auth_client.get("/api/slices", headers=headers).status_code == 200

    def test_bearer_and_x_api_key_headers_both_work(self, auth_client: TestClient) -> None:
        via_bearer = auth_client.get(
            "/api/slices", headers={"Authorization": "Bearer sk_read_key"}
        )
        via_x_api_key = auth_client.get("/api/slices", headers={"X-API-Key": "sk_read_key"})
        assert via_bearer.status_code == via_x_api_key.status_code == 200

    def test_health_and_readiness_stay_open_without_a_key(
        self, auth_client: TestClient
    ) -> None:
        assert auth_client.get("/health").status_code == 200
        assert auth_client.get("/api/system/readiness").status_code == 200

    def test_metrics_requires_a_key_once_auth_is_enabled(self, auth_client: TestClient) -> None:
        assert auth_client.get("/metrics").status_code == 401
        assert (
            auth_client.get("/metrics", headers={"X-API-Key": "sk_read_key"}).status_code
            == 200
        )

    def test_audit_log_records_the_authenticated_actor(self, auth_client: TestClient) -> None:
        headers = {"X-API-Key": "sk_write_key"}
        auth_client.post(
            "/api/slices/provision",
            json={"intent": "iot slice with 5 Mbps in Pune"},
            headers=headers,
        )
        events = auth_client.get("/api/events", headers=headers).json()
        assert events[0]["actor"] == "ops-team"

    def test_scale_threads_the_authenticated_principal_through(
        self, auth_client: TestClient
    ) -> None:
        # scale_slice() calls update_slice() as a plain Python coroutine, not
        # over HTTP, so FastAPI's dependency injection never runs for that
        # inner call - the principal must be passed through explicitly or the
        # audit trail for a scale action would misattribute to "system".
        headers = {"X-API-Key": "sk_write_key"}
        provisioned = auth_client.post(
            "/api/slices/provision",
            json={"intent": "iot slice with 20 Mbps in Pune"},
            headers=headers,
        ).json()
        slice_id = provisioned["slice_config"]["slice_id"]

        auth_client.post(
            f"/api/slices/{slice_id}/scale", json={"factor": 2}, headers=headers
        )
        events = auth_client.get(
            "/api/events", params={"slice_id": slice_id, "event_type": "slice_updated"},
            headers=headers,
        ).json()
        assert events[0]["actor"] == "ops-team"


class TestOpenByDefault:
    def test_without_any_configured_keys_every_request_is_treated_as_privileged(self) -> None:
        # No monkeypatch here: this exercises the actual default state.
        with TestClient(app) as client:
            assert client.get("/api/slices").status_code == 200
            response = client.post(
                "/api/slices/provision", json={"intent": "iot slice with 5 Mbps in Pune"}
            )
            assert response.status_code == 200
