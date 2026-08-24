"""Integration tests for the slice API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from services.slice_registry import slice_registry


@pytest.fixture
def client() -> TestClient:
    saved = slice_registry.get_all_slices()
    with TestClient(app) as test_client:
        yield test_client
    slice_registry.clear()
    for config in saved:
        slice_registry.add_slice(config)


def provision(client: TestClient, intent: str) -> dict:
    response = client.post("/api/slices/provision", json={"intent": intent})
    assert response.status_code == 200, response.text
    return response.json()


class TestSystemEndpoints:
    def test_health(self, client: TestClient) -> None:
        assert client.get("/health").json()["status"] == "healthy"

    def test_root_lists_the_api_surface(self, client: TestClient) -> None:
        assert "provision_slice" in client.get("/").json()["endpoints"]

    def test_readiness_is_true_without_an_llm_key(self, client: TestClient) -> None:
        assert client.get("/api/system/readiness").json()["ready"] is True

    def test_parser_status_reports_the_deterministic_parser(self, client: TestClient) -> None:
        assert client.get("/api/system/parser").json()["active_parser"] == "rule-based"


class TestProvisioning:
    def test_provisioning_activates_a_slice(self, client: TestClient) -> None:
        result = provision(client, "IoT slice for 4000 smart meters in Pune with 20 Mbps")
        assert result["success"] is True
        assert result["slice_config"]["status"] == "active"
        assert result["parser_used"] == "rule-based"
        assert result["deploy_time_seconds"] >= 0

    def test_a_provisioned_slice_is_readable_back(self, client: TestClient) -> None:
        slice_id = provision(client, "broadband slice with 30 Mbps in Delhi")["slice_config"]["slice_id"]
        assert client.get(f"/api/slices/{slice_id}").status_code == 200

    def test_a_blank_intent_is_rejected_at_the_schema_boundary(self, client: TestClient) -> None:
        # Whitespace-only input fails Pydantic validation (422) rather than
        # reaching the parser and failing there (400) - rejected earlier and
        # consistently with every other validation error in the API.
        assert client.post("/api/slices/provision", json={"intent": "   "}).status_code == 422

    def test_an_oversized_intent_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/slices/provision", json={"intent": "x" * 2001}
        )
        assert response.status_code == 422

    def test_an_oversized_request_reports_the_conflict(self, client: TestClient) -> None:
        result = provision(client, "broadband slice with 50 Gbps for the campus")
        assert result["success"] is False
        assert result["conflict_report"]["has_conflict"] is True
        assert result["conflict_report"]["auto_remediation"]

    def test_missing_slice_returns_404(self, client: TestClient) -> None:
        assert client.get("/api/slices/nope").status_code == 404


class TestSimulation:
    def test_simulation_does_not_create_a_slice(self, client: TestClient) -> None:
        before = len(client.get("/api/slices").json())
        client.post("/api/slices/simulate", json={"intent": "iot slice with 10 Mbps in Pune"})
        assert len(client.get("/api/slices").json()) == before

    def test_simulation_reports_the_capacity_delta(self, client: TestClient) -> None:
        result = client.post(
            "/api/slices/simulate", json={"intent": "broadband slice with 100 Mbps in Delhi"}
        ).json()
        assert result["capacity_after_mbps"] == pytest.approx(
            result["capacity_before_mbps"] + 100.0
        )

    def test_remediation_turns_a_blocked_intent_into_a_deployable_one(
        self, client: TestClient
    ) -> None:
        result = client.post(
            "/api/slices/simulate",
            json={"intent": "broadband slice with 40 Gbps in Delhi", "apply_remediation": True},
        ).json()
        assert result["would_deploy"] is False
        assert result["remediated_report"]["has_conflict"] is False


class TestLifecycle:
    def test_patch_updates_a_field(self, client: TestClient) -> None:
        slice_id = provision(client, "iot slice with 10 Mbps in Pune")["slice_config"]["slice_id"]
        updated = client.patch(f"/api/slices/{slice_id}", json={"latency_ms": 45}).json()
        assert updated["latency_ms"] == 45
        assert updated["updated_at"] is not None

    def test_patch_with_no_fields_is_rejected(self, client: TestClient) -> None:
        slice_id = provision(client, "iot slice with 10 Mbps in Pune")["slice_config"]["slice_id"]
        assert client.patch(f"/api/slices/{slice_id}", json={}).status_code == 400

    def test_patch_beyond_capacity_returns_409(self, client: TestClient) -> None:
        slice_id = provision(client, "iot slice with 10 Mbps in Pune")["slice_config"]["slice_id"]
        response = client.patch(
            f"/api/slices/{slice_id}", json={"guaranteed_bitrate_mbps": 99_000}
        )
        assert response.status_code == 409

    def test_scaling_by_a_factor(self, client: TestClient) -> None:
        slice_id = provision(client, "iot slice with 20 Mbps in Pune")["slice_config"]["slice_id"]
        scaled = client.post(f"/api/slices/{slice_id}/scale", json={"factor": 2}).json()
        assert scaled["guaranteed_bitrate_mbps"] == pytest.approx(40.0)

    def test_scaling_without_arguments_is_rejected(self, client: TestClient) -> None:
        slice_id = provision(client, "iot slice with 20 Mbps in Pune")["slice_config"]["slice_id"]
        assert client.post(f"/api/slices/{slice_id}/scale", json={}).status_code == 400

    def test_suspend_releases_bandwidth_and_resume_reclaims_it(self, client: TestClient) -> None:
        slice_id = provision(client, "iot slice with 25 Mbps in Pune")["slice_config"]["slice_id"]
        used_before = client.get("/api/slices/stats/breakdown").json()["used_mbps"]

        assert client.post(f"/api/slices/{slice_id}/suspend").json()["new_status"] == "pending"
        used_suspended = client.get("/api/slices/stats/breakdown").json()["used_mbps"]
        assert used_suspended == pytest.approx(used_before - 25.0)

        assert client.post(f"/api/slices/{slice_id}/resume").json()["new_status"] == "active"
        assert client.get("/api/slices/stats/breakdown").json()["used_mbps"] == pytest.approx(
            used_before
        )

    def test_suspending_twice_returns_409(self, client: TestClient) -> None:
        slice_id = provision(client, "iot slice with 10 Mbps in Pune")["slice_config"]["slice_id"]
        client.post(f"/api/slices/{slice_id}/suspend")
        assert client.post(f"/api/slices/{slice_id}/suspend").status_code == 409

    def test_concurrent_delete_of_the_same_slice_returns_404_not_a_crash(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # DELETE awaits the SDN controller between checking the slice exists
        # and actually removing it from the registry, so a second concurrent
        # DELETE for the same slice can win that race and delete it first.
        # Simulated here by having the controller itself delete the slice as
        # a side effect during that await, mimicking what a second request
        # completing in between would do.
        from routers import slices as slices_router

        slice_id = provision(client, "iot slice with 10 Mbps in Pune")["slice_config"][
            "slice_id"
        ]
        original_remove = slices_router.sdn_controller.remove_slice

        async def remove_and_race(sid: str) -> bool:
            slices_router.slice_registry.delete_slice(sid)
            return await original_remove(sid)

        monkeypatch.setattr(slices_router.sdn_controller, "remove_slice", remove_and_race)

        response = client.delete(f"/api/slices/{slice_id}")

        assert response.status_code == 404
        assert "already deleted" in response.json()["detail"]

    def test_delete_reports_the_bandwidth_it_released(self, client: TestClient) -> None:
        slice_id = provision(client, "iot slice with 15 Mbps in Pune")["slice_config"]["slice_id"]
        body = client.delete(f"/api/slices/{slice_id}").json()
        assert body["released_mbps"] == pytest.approx(15.0)
        assert client.get(f"/api/slices/{slice_id}").status_code == 404


class TestIdempotency:
    def test_a_repeated_key_returns_the_same_slice(self, client: TestClient) -> None:
        body = {"intent": "iot slice with 15 Mbps in Pune"}
        headers = {"Idempotency-Key": "retry-1"}
        first = client.post("/api/slices/provision", json=body, headers=headers).json()
        second = client.post("/api/slices/provision", json=body, headers=headers).json()
        assert first["slice_config"]["slice_id"] == second["slice_config"]["slice_id"]

    def test_a_repeated_key_does_not_provision_twice(self, client: TestClient) -> None:
        body = {"intent": "iot slice with 16 Mbps in Nashik"}
        headers = {"Idempotency-Key": "retry-2"}
        before = len(client.get("/api/slices").json())
        client.post("/api/slices/provision", json=body, headers=headers)
        client.post("/api/slices/provision", json=body, headers=headers)
        after = len(client.get("/api/slices").json())
        assert after == before + 1

    def test_a_different_key_provisions_a_new_slice(self, client: TestClient) -> None:
        body = {"intent": "iot slice with 17 Mbps in Kochi"}
        first = client.post(
            "/api/slices/provision", json=body, headers={"Idempotency-Key": "retry-a"}
        ).json()
        second = client.post(
            "/api/slices/provision", json=body, headers={"Idempotency-Key": "retry-b"}
        ).json()
        assert first["slice_config"]["slice_id"] != second["slice_config"]["slice_id"]

    def test_no_key_at_all_is_never_deduplicated(self, client: TestClient) -> None:
        body = {"intent": "iot slice with 18 Mbps in Indore"}
        first = client.post("/api/slices/provision", json=body).json()
        second = client.post("/api/slices/provision", json=body).json()
        assert first["slice_config"]["slice_id"] != second["slice_config"]["slice_id"]

    def test_a_conflicting_result_is_also_cached(self, client: TestClient) -> None:
        body = {"intent": "broadband slice with 50 Gbps for the campus"}
        headers = {"Idempotency-Key": "retry-conflict"}
        first = client.post("/api/slices/provision", json=body, headers=headers).json()
        second = client.post("/api/slices/provision", json=body, headers=headers).json()
        assert first["success"] is False
        assert first == second


class TestQueries:
    def test_filters_narrow_the_listing(self, client: TestClient) -> None:
        provision(client, "iot slice for smart meters with 10 Mbps in Nagpur")
        by_location = client.get("/api/slices", params={"location": "Nagpur"}).json()
        assert by_location and all(s["location"] == "Nagpur" for s in by_location)
        assert client.get("/api/slices", params={"status": "conflict"}).json() == []

    def test_stats_and_breakdown_agree_on_usage(self, client: TestClient) -> None:
        stats = client.get("/api/slices/stats/summary").json()
        breakdown = client.get("/api/slices/stats/breakdown").json()
        assert stats["total_bandwidth_used_mbps"] == pytest.approx(breakdown["used_mbps"])
