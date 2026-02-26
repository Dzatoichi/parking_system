"""
tests/integration/test_spot_dao.py

Интеграционные тесты DAO — работают с реальной (SQLite) базой данных.
Проверяют, что SQL-запросы написаны правильно.

Каждый тест работает внутри транзакции, которая откатывается в conftest.py.
"""

import pytest
import pytest_asyncio

from src.dao.spot_dao import SpotDAO
from src.models.spots.spot import Spot
from src.models.spots.status.spot_status import SpotStatus
from src.models.spots.type.spot_type import SpotType
from tests.conftest import make_spot


# ──────────────────────────────────────────────────────────────
# Вспомогательная фикстура: DAO + несколько записей в БД
# ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def dao(session):
    return SpotDAO(session)


@pytest_asyncio.fixture
async def seeded(session, dao) -> list[Spot]:
    """Добавляет 3 места: 2 FREE, 1 OCCUPIED."""
    spots = [
        make_spot(parking_id=1, spot_number="A-01", spot_status=SpotStatus.FREE),
        make_spot(parking_id=1, spot_number="A-02", spot_status=SpotStatus.FREE),
        make_spot(
            parking_id=1,
            spot_number="B-01",
            spot_status=SpotStatus.OCCUPIED,
            current_vehicle_id=10,
        ),
    ]
    session.add_all(spots)
    await session.flush()
    for s in spots:
        await session.refresh(s)
    return spots


# ──────────────────────────────────────────────────────────────
# get_by_id
# ──────────────────────────────────────────────────────────────

class TestGetById:
    @pytest.mark.asyncio
    async def test_returns_spot(self, dao, seeded):
        spot = await dao.get_by_id(seeded[0].id)
        assert spot is not None
        assert spot.spot_number == "A-01"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_id(self, dao):
        spot = await dao.get_by_id(99999)
        assert spot is None


# ──────────────────────────────────────────────────────────────
# get_by_parking
# ──────────────────────────────────────────────────────────────

class TestGetByParking:
    @pytest.mark.asyncio
    async def test_returns_all_spots(self, dao, seeded):
        spots, total = await dao.get_by_parking(parking_id=1)
        assert total == 3
        assert len(spots) == 3

    @pytest.mark.asyncio
    async def test_filters_by_status(self, dao, seeded):
        spots, total = await dao.get_by_parking(parking_id=1, status=SpotStatus.FREE)
        assert total == 2
        assert all(s.spot_status == SpotStatus.FREE for s in spots)

    @pytest.mark.asyncio
    async def test_pagination_offset(self, dao, seeded):
        spots, total = await dao.get_by_parking(parking_id=1, offset=2, limit=10)
        assert total == 3     # общее — 3
        assert len(spots) == 1  # на странице — 1 (пропустили 2)

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_parking(self, dao, seeded):
        spots, total = await dao.get_by_parking(parking_id=9999)
        assert total == 0
        assert spots == []

    @pytest.mark.asyncio
    async def test_results_ordered_by_spot_number(self, dao, seeded):
        spots, _ = await dao.get_by_parking(parking_id=1)
        numbers = [s.spot_number for s in spots]
        assert numbers == sorted(numbers)


# ──────────────────────────────────────────────────────────────
# get_by_number
# ──────────────────────────────────────────────────────────────

class TestGetByNumber:
    @pytest.mark.asyncio
    async def test_finds_existing_number(self, dao, seeded):
        spot = await dao.get_by_number(parking_id=1, spot_number="A-01")
        assert spot is not None
        assert spot.spot_number == "A-01"

    @pytest.mark.asyncio
    async def test_returns_none_for_different_parking(self, dao, seeded):
        # Место A-01 есть в parking_id=1, но не в parking_id=2
        spot = await dao.get_by_number(parking_id=2, spot_number="A-01")
        assert spot is None


# ──────────────────────────────────────────────────────────────
# get_stats
# ──────────────────────────────────────────────────────────────

class TestGetStats:
    @pytest.mark.asyncio
    async def test_counts_by_status(self, dao, seeded):
        stats = await dao.get_stats(parking_id=1)
        assert stats["free"] == 2
        assert stats["occupied"] == 1
        assert stats["reserved"] == 0
        assert stats["total"] == 3

    @pytest.mark.asyncio
    async def test_returns_zeros_for_empty_parking(self, dao):
        stats = await dao.get_stats(parking_id=9999)
        assert stats == {"free": 0, "occupied": 0, "reserved": 0, "total": 0}


# ──────────────────────────────────────────────────────────────
# create
# ──────────────────────────────────────────────────────────────

class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_and_returns_with_id(self, dao, session):
        spot = make_spot(parking_id=1, spot_number="Z-99")
        created = await dao.create(spot)

        assert created.id is not None
        assert created.spot_number == "Z-99"

    @pytest.mark.asyncio
    async def test_created_spot_is_queryable(self, dao, session):
        spot = make_spot(parking_id=1, spot_number="Z-88")
        created = await dao.create(spot)

        fetched = await dao.get_by_id(created.id)
        assert fetched is not None
        assert fetched.spot_number == "Z-88"


# ──────────────────────────────────────────────────────────────
# update_status
# ──────────────────────────────────────────────────────────────

class TestUpdateStatus:
    @pytest.mark.asyncio
    async def test_sets_occupied_and_vehicle(self, dao, seeded):
        spot_id = seeded[0].id  # A-01, FREE

        updated = await dao.update_status(
            spot_id=spot_id,
            new_status=SpotStatus.OCCUPIED,
            vehicle_id=42,
        )

        assert updated.spot_status == SpotStatus.OCCUPIED
        assert updated.current_vehicle_id == 42
        assert updated.occupied_since is not None

    @pytest.mark.asyncio
    async def test_free_clears_vehicle_and_occupied_since(self, dao, seeded):
        spot_id = seeded[2].id  # B-01, OCCUPIED

        updated = await dao.update_status(
            spot_id=spot_id,
            new_status=SpotStatus.FREE,
            vehicle_id=None,
        )

        assert updated.spot_status == SpotStatus.FREE
        assert updated.current_vehicle_id is None
        assert updated.occupied_since is None

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_id(self, dao):
        result = await dao.update_status(
            spot_id=99999, new_status=SpotStatus.FREE
        )
        assert result is None


# ──────────────────────────────────────────────────────────────
# update_coordinates
# ──────────────────────────────────────────────────────────────

class TestUpdateCoordinates:
    @pytest.mark.asyncio
    async def test_updates_coordinates(self, dao, seeded):
        spot_id = seeded[0].id
        new_coords = {
            "points": [[1.0, 1.0], [9.0, 1.0], [9.0, 9.0], [1.0, 9.0]],
            "center_x": 5.0,
            "center_y": 5.0,
        }

        updated = await dao.update_coordinates(spot_id=spot_id, coordinates=new_coords)

        assert updated.spot_coordinates == new_coords


# ──────────────────────────────────────────────────────────────
# delete
# ──────────────────────────────────────────────────────────────

class TestDelete:
    @pytest.mark.asyncio
    async def test_deletes_existing_spot(self, dao, seeded):
        spot_id = seeded[0].id
        result = await dao.delete(spot_id)

        assert result is True
        assert await dao.get_by_id(spot_id) is None

    @pytest.mark.asyncio
    async def test_returns_false_for_missing_spot(self, dao):
        result = await dao.delete(99999)
        assert result is False
