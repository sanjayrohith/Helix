"""Tests for ETag-based optimistic concurrency on slice updates."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.etag import compute_etag, matches
from main import app
from models.slice_models import SliceConfig
from services.slice_registry import slice_registry


@pytest.fixture
def client() -> TestClient:
    saved = slice_registry.get_all_slices()
    with TestClient(app) as test_client:
        yield test_client
    slice_registry.clear()
    for config in saved:
        slice_registry.add_slice(config)


def make_slice(**overrides) -> SliceConfig:
    payload = {
        "slice_id": "etag-test",
        "name": "ETag Test",
        "sst": 1,
        "sd": "0x00ee00",
        "qos_5qi": 9,
        "arp_priority": 5,
        "guaranteed_bitrate_mbps": 50.0,
        "max_bitrate_mbps": 100.0,
        "latency_ms": 20,
        "security_level": "standard",
        "isolation": "shared",
        "device_count": 10,
        "use_case": "broadband",
        "location": "Pune",
        "status": "active",
    }
    payload.update(overrides)
    return SliceConfig(**payload)


class TestEtagComputation:
    def test_identical_content_produces_the_same_etag(self) -> None:
        # created_at defaults to "now": pin it, or two calls a microsecond
        # apart would differ in content and this would not test what it
        # claims to.
        from models.slice_models import utcnow

        fixed = utcnow()
        assert compute_etag(make_slice(created_at=fixed)) == compute_etag(
            make_slice(created_at=fixed)
        )

    def test_different_content_produces_a_different_etag(self) -> None:
        assert compute_etag(make_slice()) != compute_etag(make_slice(latency_ms=5))

    def test_the_etag_is_a_quoted_string(self) -> None:
        etag = compute_etag(make_slice())
        assert etag.startswith('"') and etag.endswith('"')


class TestIfMatchParsing:
    def test_a_wildcard_matches_anything(self) -> None:
        assert matches('"abc123"', "*")

    def test_an_exact_match_succeeds(self) -> None:
        assert matches('"abc123"', '"abc123"')

    def test_a_mismatch_fails(self) -> None:
        assert not matches('"abc123"', '"different"')

    def test_a_comma_separated_list_matches_if_any_entry_matches(self) -> None:
        assert matches('"abc123"', '"nope", "abc123", "also-nope"')


class TestApiEnforcement:
    def test_get_sets_an_etag_header(self, client: TestClient) -> None:
        provisioned = client.post(
            "/api/slices/provision", json={"intent": "iot slice with 10 Mbps in Pune"}
        ).json()
        slice_id = provisioned["slice_config"]["slice_id"]
        response = client.get(f"/api/slices/{slice_id}")
        assert response.headers["ETag"]

    def test_patch_without_if_match_is_unconditional(self, client: TestClient) -> None:
        provisioned = client.post(
            "/api/slices/provision", json={"intent": "iot slice with 10 Mbps in Pune"}
        ).json()
        slice_id = provisioned["slice_config"]["slice_id"]
        response = client.patch(f"/api/slices/{slice_id}", json={"latency_ms": 33})
        assert response.status_code == 200

    def test_patch_with_a_matching_if_match_succeeds(self, client: TestClient) -> None:
        provisioned = client.post(
            "/api/slices/provision", json={"intent": "iot slice with 10 Mbps in Pune"}
        ).json()
        slice_id = provisioned["slice_config"]["slice_id"]
        etag = client.get(f"/api/slices/{slice_id}").headers["ETag"]

        response = client.patch(
            f"/api/slices/{slice_id}", json={"latency_ms": 33}, headers={"If-Match": etag}
        )
        assert response.status_code == 200

    def test_patch_with_a_stale_if_match_is_rejected_with_412(
        self, client: TestClient
    ) -> None:
        provisioned = client.post(
            "/api/slices/provision", json={"intent": "iot slice with 10 Mbps in Pune"}
        ).json()
        slice_id = provisioned["slice_config"]["slice_id"]
        stale_etag = client.get(f"/api/slices/{slice_id}").headers["ETag"]

        # Someone else's write lands first.
        client.patch(f"/api/slices/{slice_id}", json={"latency_ms": 44})

        response = client.patch(
            f"/api/slices/{slice_id}", json={"latency_ms": 55}, headers={"If-Match": stale_etag}
        )
        assert response.status_code == 412

    def test_a_rejected_update_does_not_apply(self, client: TestClient) -> None:
        provisioned = client.post(
            "/api/slices/provision", json={"intent": "iot slice with 10 Mbps in Pune"}
        ).json()
        slice_id = provisioned["slice_config"]["slice_id"]
        stale_etag = client.get(f"/api/slices/{slice_id}").headers["ETag"]
        client.patch(f"/api/slices/{slice_id}", json={"latency_ms": 44})

        client.patch(
            f"/api/slices/{slice_id}", json={"latency_ms": 999}, headers={"If-Match": stale_etag}
        )

        current = client.get(f"/api/slices/{slice_id}").json()
        assert current["latency_ms"] == 44

    def test_patch_returns_a_fresh_etag_reflecting_the_new_state(
        self, client: TestClient
    ) -> None:
        provisioned = client.post(
            "/api/slices/provision", json={"intent": "iot slice with 10 Mbps in Pune"}
        ).json()
        slice_id = provisioned["slice_config"]["slice_id"]
        before = client.get(f"/api/slices/{slice_id}").headers["ETag"]

        response = client.patch(f"/api/slices/{slice_id}", json={"latency_ms": 77})
        after_patch_etag = response.headers["ETag"]
        after_get_etag = client.get(f"/api/slices/{slice_id}").headers["ETag"]

        assert after_patch_etag != before
        assert after_patch_etag == after_get_etag

    def test_wildcard_if_match_always_succeeds(self, client: TestClient) -> None:
        provisioned = client.post(
            "/api/slices/provision", json={"intent": "iot slice with 10 Mbps in Pune"}
        ).json()
        slice_id = provisioned["slice_config"]["slice_id"]
        response = client.patch(
            f"/api/slices/{slice_id}", json={"latency_ms": 88}, headers={"If-Match": "*"}
        )
        assert response.status_code == 200

    def test_scale_is_unconditional_and_returns_an_etag(self, client: TestClient) -> None:
        # /scale has no If-Match parameter of its own; this asserts it still
        # goes through the shared update path cleanly (the direct-call
        # footgun this endpoint hit twice while ETag support was added).
        provisioned = client.post(
            "/api/slices/provision", json={"intent": "iot slice with 20 Mbps in Pune"}
        ).json()
        slice_id = provisioned["slice_config"]["slice_id"]
        response = client.post(f"/api/slices/{slice_id}/scale", json={"factor": 2})
        assert response.status_code == 200
        assert response.headers["ETag"]
        assert response.json()["guaranteed_bitrate_mbps"] == pytest.approx(40.0)
