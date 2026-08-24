"""Tests for header-based pagination on list endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from services.slice_registry import slice_registry


@pytest.fixture
def client() -> TestClient:
    # Isolate from the module-level registry singleton other test files
    # also touch, matching the pattern in tests/test_api_slices.py.
    saved = slice_registry.get_all_slices()
    with TestClient(app) as test_client:
        yield test_client
    slice_registry.clear()
    for config in saved:
        slice_registry.add_slice(config)


def seed_slices(client: TestClient, count: int) -> None:
    for i in range(count):
        client.post(
            "/api/slices/provision",
            json={"intent": f"iot slice with {i + 1} Mbps in PagTest{i}"},
        )


class TestSlicePagination:
    def test_default_request_is_still_a_bare_array(self, client: TestClient) -> None:
        response = client.get("/api/slices")
        assert isinstance(response.json(), list)

    def test_limit_caps_the_page_size(self, client: TestClient) -> None:
        seed_slices(client, 5)
        response = client.get("/api/slices", params={"limit": 2})
        assert len(response.json()) == 2

    def test_x_total_count_reflects_the_full_filtered_set(self, client: TestClient) -> None:
        seed_slices(client, 5)
        response = client.get("/api/slices", params={"limit": 2, "location": "PagTest0"})
        assert response.headers["X-Total-Count"] == "1"

    def test_offset_advances_the_page(self, client: TestClient) -> None:
        seed_slices(client, 4)
        first = client.get("/api/slices", params={"limit": 2, "offset": 0}).json()
        second = client.get("/api/slices", params={"limit": 2, "offset": 2}).json()
        first_ids = {slice_["slice_id"] for slice_ in first}
        second_ids = {slice_["slice_id"] for slice_ in second}
        assert first_ids.isdisjoint(second_ids)

    def test_link_header_offers_next_on_the_first_page(self, client: TestClient) -> None:
        seed_slices(client, 5)
        response = client.get("/api/slices", params={"limit": 2, "offset": 0})
        assert 'rel="next"' in response.headers["Link"]
        assert 'rel="prev"' not in response.headers["Link"]

    def test_link_header_offers_prev_on_a_later_page(self, client: TestClient) -> None:
        seed_slices(client, 5)
        response = client.get("/api/slices", params={"limit": 2, "offset": 2})
        assert 'rel="prev"' in response.headers["Link"]

    def test_the_last_page_has_no_next_link(self, client: TestClient) -> None:
        seed_slices(client, 3)
        total = int(client.get("/api/slices").headers["X-Total-Count"])
        response = client.get("/api/slices", params={"limit": 500, "offset": 0})
        assert len(response.json()) == total
        assert 'rel="next"' not in response.headers.get("Link", "")

    def test_limit_above_the_maximum_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/slices", params={"limit": 100_000}).status_code == 422

    def test_negative_offset_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/slices", params={"offset": -1}).status_code == 422


class TestEventPagination:
    def test_default_request_is_still_a_bare_array(self, client: TestClient) -> None:
        assert isinstance(client.get("/api/events").json(), list)

    def test_x_total_count_is_present(self, client: TestClient) -> None:
        seed_slices(client, 2)
        response = client.get("/api/events", params={"limit": 1})
        assert int(response.headers["X-Total-Count"]) >= 2

    def test_offset_pages_through_distinct_events(self, client: TestClient) -> None:
        seed_slices(client, 5)
        first = client.get("/api/events", params={"limit": 3, "offset": 0}).json()
        second = client.get("/api/events", params={"limit": 3, "offset": 3}).json()
        first_ids = {event["event_id"] for event in first}
        second_ids = {event["event_id"] for event in second}
        assert first_ids.isdisjoint(second_ids)
