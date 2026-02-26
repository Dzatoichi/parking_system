"""
tests/e2e/test_spots_router.py

E2E-тесты роутера — запросы идут через реальный HTTP-клиент (httpx).
Сервис не мокается: используется реальный SpotService с тестовой SQLite-сессией.
Проверяем HTTP-статусы, структуру JSON-ответов и работу query-параметров.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.models.spots.spot import Spot
from src.models.spots.status.spot_status import SpotStatus
from src.models.spots.type.spot_type import SpotType
from tests.conftest import make_spot, make_spot_create_payload


# ──────────────────────────────────────────────────────────────
# Фикстура: несколько мест в БД
# ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_spots(session) -> list[Spot]:
    spots = [
        make_spot(parking_id=1, spot_number="A-01"),
        make_spot(parking_id=1, spot_number="A-02"),
        make_spot(
            parking_id=1,
            spot_number="B-01",
            spot_status=SpotStatus.OCCUPIED,
            current_vehicle_id=5,
        ),
    ]
    session.add_all(spots)
    await session.flush()
    for s in spots:
        await session.refresh(s)
    return spots


# ──────────────────────────────────────────────────────────────
# GET /{parking_id} — список мест
# ──────────────────────────────────────────────────────────────

class TestGetSpots:
    @pytest.mark.asyncio
    async def test_returns_200_with_paginated_list(self, client: AsyncClient, seeded_spots):
        resp = await client.get("/spots/1")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert body["page"] == 1

    @pytest.mark.asyncio
    async def test_filters_by_status(self, client: AsyncClient, seeded_spots):
        resp = await client.get("/spots/1?status=free")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert all(s["spot_status"] == "free" for s in body["items"])

    @pytest.mark.asyncio
    async def test_pagination_size(self, client: AsyncClient, seeded_spots):
        resp = await client.get("/spots/1?size=2&page=1")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 3
        assert body["pages"] == 2

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_parking(self, client: AsyncClient):
        resp = await client.get("/spots/9999")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_invalid_status_returns_422(self, client: AsyncClient):
        resp = await client.get("/spots/1?status=flying")
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────
# GET /{parking_id}/stats
# ──────────────────────────────────────────────────────────────

class TestGetStats:
    @pytest.mark.asyncio
    async def test_returns_correct_counts(self, client: AsyncClient, seeded_spots):
        resp = await client.get("/spots/1/stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_spots"] == 3
        assert body["free"] == 2
        assert body["occupied"] == 1
        assert body["reserved"] == 0
        assert 0.0 <= body["occupancy_rate"] <= 1.0


# ──────────────────────────────────────────────────────────────
# GET /detail/{spot_id}
# ──────────────────────────────────────────────────────────────

class TestGetSpotDetail:
    @pytest.mark.asyncio
    async def test_returns_spot_with_coordinates(self, client: AsyncClient, seeded_spots):
        spot_id = seeded_spots[0].id
        resp = await client.get(f"/spots/detail/{spot_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == spot_id
        assert "spot_coordinates" in body
        assert "points" in body["spot_coordinates"]

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown(self, client: AsyncClient):
        resp = await client.get("/spots/detail/99999")
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────
# POST /{parking_id} — создание места
# ──────────────────────────────────────────────────────────────

class TestCreateSpot:
    @pytest.mark.asyncio
    async def test_creates_spot_returns_201(self, client: AsyncClient):
        payload = make_spot_create_payload("C-01")
        resp = await client.post("/spots/1", json=payload)

        assert resp.status_code == 201
        body = resp.json()
        assert body["spot_number"] == "C-01"
        assert body["spot_status"] == "free"
        assert body["id"] is not None

    @pytest.mark.asyncio
    async def test_returns_409_on_duplicate(self, client: AsyncClient, seeded_spots):
        # A-01 уже существует в seeded_spots
        payload = make_spot_create_payload("A-01")
        resp = await client.post("/spots/1", json=payload)

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_returns_422_on_invalid_payload(self, client: AsyncClient):
        resp = await client.post("/spots/1", json={"spot_number": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_422_on_invalid_spot_number_chars(self, client: AsyncClient):
        payload = make_spot_create_payload("A 01!")  # пробел и ! — недопустимо
        resp = await client.post("/spots/1", json=payload)
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────
# POST /{parking_id}/bulk
# ──────────────────────────────────────────────────────────────

class TestCreateSpotsBulk:
    @pytest.mark.asyncio
    async def test_creates_multiple_spots(self, client: AsyncClient):
        payload = [
            make_spot_create_payload("D-01"),
            make_spot_create_payload("D-02"),
            make_spot_create_payload("D-03"),
        ]
        resp = await client.post("/spots/2/bulk", json=payload)

        assert resp.status_code == 201
        assert len(resp.json()) == 3

    @pytest.mark.asyncio
    async def test_returns_422_on_internal_duplicates(self, client: AsyncClient):
        payload = [
            make_spot_create_payload("E-01"),
            make_spot_create_payload("E-01"),  # дубль
        ]
        resp = await client.post("/spots/3/bulk", json=payload)

        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────
# PATCH /{spot_id}/status
# ──────────────────────────────────────────────────────────────

class TestChangeStatus:
    @pytest.mark.asyncio
    async def test_free_to_occupied(self, client: AsyncClient, seeded_spots):
        spot_id = seeded_spots[0].id  # A-01, FREE
        resp = await client.patch(
            f"/spots/{spot_id}/status",
            json={"status": "occupied", "vehicle_id": 7},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["spot_status"] == "occupied"
        assert body["current_vehicle_id"] == 7

    @pytest.mark.asyncio
    async def test_occupied_to_free(self, client: AsyncClient, seeded_spots):
        spot_id = seeded_spots[2].id  # B-01, OCCUPIED
        resp = await client.patch(
            f"/spots/{spot_id}/status",
            json={"status": "free", "vehicle_id": None},
        )

        assert resp.status_code == 200
        assert resp.json()["spot_status"] == "free"

    @pytest.mark.asyncio
    async def test_returns_409_same_status(self, client: AsyncClient, seeded_spots):
        spot_id = seeded_spots[0].id  # уже FREE
        resp = await client.patch(
            f"/spots/{spot_id}/status",
            json={"status": "free"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_returns_422_occupied_without_vehicle_id(self, client: AsyncClient, seeded_spots):
        # Pydantic-валидатор должен отклонить: OCCUPIED без vehicle_id
        spot_id = seeded_spots[0].id
        resp = await client.patch(
            f"/spots/{spot_id}/status",
            json={"status": "occupied"},  # нет vehicle_id
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_spot(self, client: AsyncClient):
        resp = await client.patch(
            "/spots/99999/status",
            json={"status": "free"},
        )
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────
# PATCH /{spot_id}/coordinates
# ──────────────────────────────────────────────────────────────

class TestUpdateCoordinates:
    @pytest.mark.asyncio
    async def test_updates_free_spot(self, client: AsyncClient, seeded_spots):
        spot_id = seeded_spots[0].id
        new_coords = {
            "spot_coordinates": {
                "points": [[1.0, 1.0], [9.0, 1.0], [9.0, 9.0], [1.0, 9.0]],
                "center_x": 5.0,
                "center_y": 5.0,
            }
        }
        resp = await client.patch(f"/spots/{spot_id}/coordinates", json=new_coords)

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_409_for_occupied_spot(self, client: AsyncClient, seeded_spots):
        spot_id = seeded_spots[2].id  # B-01, OCCUPIED
        new_coords = {
            "spot_coordinates": {
                "points": [[1.0, 1.0], [9.0, 1.0], [9.0, 9.0], [1.0, 9.0]],
                "center_x": 5.0,
                "center_y": 5.0,
            }
        }
        resp = await client.patch(f"/spots/{spot_id}/coordinates", json=new_coords)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_returns_422_for_invalid_polygon(self, client: AsyncClient, seeded_spots):
        spot_id = seeded_spots[0].id
        # Только 2 точки — нарушает min_length=3
        resp = await client.patch(
            f"/spots/{spot_id}/coordinates",
            json={
                "spot_coordinates": {
                    "points": [[0.0, 0.0], [10.0, 0.0]],
                    "center_x": 5.0,
                    "center_y": 5.0,
                }
            },
        )
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────
# DELETE /{spot_id}
# ──────────────────────────────────────────────────────────────

class TestDeleteSpot:
    @pytest.mark.asyncio
    async def test_deletes_free_spot_returns_204(self, client: AsyncClient, seeded_spots):
        spot_id = seeded_spots[0].id
        resp = await client.delete(f"/spots/{spot_id}")
        assert resp.status_code == 204

        # Повторный GET должен вернуть 404
        resp2 = await client.get(f"/spots/detail/{spot_id}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_409_for_occupied_spot(self, client: AsyncClient, seeded_spots):
        spot_id = seeded_spots[2].id  # B-01, OCCUPIED
        resp = await client.delete(f"/spots/{spot_id}")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown(self, client: AsyncClient):
        resp = await client.delete("/spots/99999")
        assert resp.status_code == 404
