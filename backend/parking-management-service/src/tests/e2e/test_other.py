"""
tests/e2e/test_parking_router.py
tests/e2e/test_cameras_router.py
tests/e2e/test_vehicles_router.py

Все три в одном файле — общий тестовый клиент через conftest.py.
Если хочешь разбить по файлам — просто разрежь по классам.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from src.models.parkings import ParkingBase
from src.models.cameras import Cameras
from src.models.vehicles import Vehicles
from src.models.status.camera_status import CameraStatus
from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType

from src.routers.parking_router import parking_router
from src.routers.cameras_router import cameras_router
from src.routers.vehicles_router import vehicles_router

from src.utils.dependencies import (
    get_parking_service, get_camera_service, get_vehicle_service
)
from src.services.parking_service import ParkingService
from src.services.camera_service import CameraService
from src.services.vehicle_service import VehicleService


# ──────────────────────────────────────────────────────────────
# Клиентские фикстуры (переопределяют зависимости через реальную сессию)
# ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def parking_client(session) -> AsyncClient:
    app = FastAPI()
    app.include_router(parking_router)
    app.dependency_overrides[get_parking_service] = lambda: ParkingService(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def cameras_client(session) -> AsyncClient:
    app = FastAPI()
    app.include_router(cameras_router)
    app.dependency_overrides[get_camera_service] = lambda: CameraService(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def vehicles_client(session) -> AsyncClient:
    app = FastAPI()
    app.include_router(vehicles_router)
    app.dependency_overrides[get_vehicle_service] = lambda: VehicleService(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ──────────────────────────────────────────────────────────────
# Фикстуры данных
# ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_parking(session) -> ParkingBase:
    p = ParkingBase(
        name="Тест-парковка",
        address="ул. Ленина, 1",
        total_spots=50,
        available_spots=50,
        is_active=True,
        settings={},
    )
    session.add(p)
    await session.flush()
    await session.refresh(p)
    return p


@pytest_asyncio.fixture
async def seeded_camera(session, seeded_parking) -> Cameras:
    c = Cameras(
        rtsp_url="rtsp://192.168.1.10:554/stream",
        parking_id=seeded_parking.id,
        status=CameraStatus.ACTIVE,
    )
    session.add(c)
    await session.flush()
    await session.refresh(c)
    return c


@pytest_asyncio.fixture
async def seeded_vehicle(session) -> Vehicles:
    v = Vehicles(plate_number="А123ВС77", is_inside=False)
    session.add(v)
    await session.flush()
    await session.refresh(v)
    return v


# ══════════════════════════════════════════════════════════════
# PARKING ROUTER
# ══════════════════════════════════════════════════════════════

class TestParkingRouter:
    @pytest.mark.asyncio
    async def test_get_all_returns_200(self, parking_client, seeded_parking):
        resp = await parking_client.get("/parking")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_by_id_returns_parking(self, parking_client, seeded_parking):
        resp = await parking_client.get(f"/parking/{seeded_parking.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == seeded_parking.id

    @pytest.mark.asyncio
    async def test_get_unknown_returns_404(self, parking_client):
        resp = await parking_client.get("/parking/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_parking_returns_201(self, parking_client):
        payload = {"name": "Новая парковка", "address": "пр. Победы, 1", "total_spots": 30}
        resp = await parking_client.post("/parking", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Новая парковка"
        assert body["total_spots"] == 30

    @pytest.mark.asyncio
    async def test_create_duplicate_name_returns_409(self, parking_client, seeded_parking):
        payload = {"name": "Тест-парковка", "address": "ул. Пушкина, 1", "total_spots": 10}
        resp = await parking_client.post("/parking", json=payload)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_invalid_payload_returns_422(self, parking_client):
        resp = await parking_client.post("/parking", json={"name": "X"})  # нет address и total_spots
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_parking(self, parking_client, seeded_parking):
        resp = await parking_client.patch(
            f"/parking/{seeded_parking.id}",
            json={"is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_delete_parking_returns_204(self, parking_client, seeded_parking):
        resp = await parking_client.delete(f"/parking/{seeded_parking.id}")
        assert resp.status_code == 204

        # Повторный запрос — 404
        resp2 = await parking_client.get(f"/parking/{seeded_parking.id}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_filter_only_active(self, parking_client, session):
        inactive = ParkingBase(
            name="Неактивная", address="ул. Тест, 2",
            total_spots=5, available_spots=5, is_active=False, settings={}
        )
        session.add(inactive)
        await session.flush()

        resp = await parking_client.get("/parking?only_active=true")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(p["is_active"] for p in items)


# ══════════════════════════════════════════════════════════════
# CAMERAS ROUTER
# ══════════════════════════════════════════════════════════════

class TestCamerasRouter:
    @pytest.mark.asyncio
    async def test_get_cameras_by_parking(self, cameras_client, seeded_camera):
        resp = await cameras_client.get(f"/cameras/{seeded_camera.parking_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["cameras"][0]["id"] == seeded_camera.id

    @pytest.mark.asyncio
    async def test_get_camera_detail(self, cameras_client, seeded_camera):
        resp = await cameras_client.get(f"/cameras/detail/{seeded_camera.id}")
        assert resp.status_code == 200
        assert resp.json()["rtsp_url"] == seeded_camera.rtsp_url

    @pytest.mark.asyncio
    async def test_get_unknown_camera_returns_404(self, cameras_client):
        resp = await cameras_client.get("/cameras/detail/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_camera_returns_201(self, cameras_client, seeded_parking):
        payload = {"rtsp_url": "rtsp://10.0.0.5:554/ch1"}
        resp = await cameras_client.post(f"/cameras/{seeded_parking.id}", json=payload)
        assert resp.status_code == 201
        assert resp.json()["rtsp_url"] == "rtsp://10.0.0.5:554/ch1"

    @pytest.mark.asyncio
    async def test_create_duplicate_url_returns_409(self, cameras_client, seeded_camera):
        payload = {"rtsp_url": seeded_camera.rtsp_url}
        resp = await cameras_client.post(f"/cameras/{seeded_camera.parking_id}", json=payload)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_for_unknown_parking_returns_404(self, cameras_client):
        resp = await cameras_client.post("/cameras/99999", json={"rtsp_url": "rtsp://x:554/s"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_invalid_rtsp_returns_422(self, cameras_client, seeded_parking):
        resp = await cameras_client.post(
            f"/cameras/{seeded_parking.id}",
            json={"rtsp_url": "http://not-rtsp.com"},  # должна сработать валидация
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_camera_returns_204(self, cameras_client, seeded_camera):
        resp = await cameras_client.delete(f"/cameras/{seeded_camera.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_unknown_returns_404(self, cameras_client):
        resp = await cameras_client.delete("/cameras/99999")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# VEHICLES ROUTER
# ══════════════════════════════════════════════════════════════

class TestVehiclesRouter:
    @pytest.mark.asyncio
    async def test_get_all_vehicles(self, vehicles_client, seeded_vehicle):
        resp = await vehicles_client.get("/vehicles")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_vehicle_by_id(self, vehicles_client, seeded_vehicle):
        resp = await vehicles_client.get(f"/vehicles/{seeded_vehicle.id}")
        assert resp.status_code == 200
        assert resp.json()["plate_number"] == "А123ВС77"

    @pytest.mark.asyncio
    async def test_get_vehicle_by_plate(self, vehicles_client, seeded_vehicle):
        resp = await vehicles_client.get("/vehicles/by-plate/А123ВС77")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_unknown_returns_404(self, vehicles_client):
        resp = await vehicles_client.get("/vehicles/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_register_vehicle_returns_201(self, vehicles_client):
        resp = await vehicles_client.post("/vehicles", json={"plate_number": "B456CD"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["plate_number"] == "B456CD"
        assert body["is_inside"] is False

    @pytest.mark.asyncio
    async def test_register_duplicate_plate_returns_409(self, vehicles_client, seeded_vehicle):
        resp = await vehicles_client.post("/vehicles", json={"plate_number": "А123ВС77"})
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_invalid_plate_returns_422(self, vehicles_client):
        resp = await vehicles_client.post("/vehicles", json={"plate_number": "ab"})  # слишком короткий
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_location_event_creates_vehicle_if_new(self, vehicles_client):
        payload = {
            "plate_number": "NEW001",
            "camera_id": 1,
            "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100},
            "event_type": "enter",
            "timestamp": "2025-01-01T12:00:00Z",
        }
        resp = await vehicles_client.post("/vehicles/location", json=payload)
        assert resp.status_code == 200
        assert resp.json()["is_inside"] is True

    @pytest.mark.asyncio
    async def test_location_event_invalid_type_returns_422(self, vehicles_client):
        payload = {
            "plate_number": "А123ВС77",
            "camera_id": 1,
            "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100},
            "event_type": "flying",  # недопустимый тип
            "timestamp": "2025-01-01T12:00:00Z",
        }
        resp = await vehicles_client.post("/vehicles/location", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_history(self, vehicles_client, seeded_vehicle):
        resp = await vehicles_client.get(f"/vehicles/{seeded_vehicle.id}/history")
        assert resp.status_code == 200
        body = resp.json()
        assert "events" in body
        assert body["vehicle_id"] == seeded_vehicle.id

    @pytest.mark.asyncio
    async def test_delete_vehicle_not_inside(self, vehicles_client, seeded_vehicle):
        resp = await vehicles_client.delete(f"/vehicles/{seeded_vehicle.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_vehicle_inside_returns_409(self, vehicles_client, session):
        inside = Vehicles(plate_number="INSIDE01", is_inside=True)
        session.add(inside)
        await session.flush()
        await session.refresh(inside)

        resp = await vehicles_client.delete(f"/vehicles/{inside.id}")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_filter_only_inside(self, vehicles_client, session):
        v = Vehicles(plate_number="INCAR777", is_inside=True)
        session.add(v)
        await session.flush()

        resp = await vehicles_client.get("/vehicles?only_inside=true")
        assert resp.status_code == 200
        assert all(v["is_inside"] for v in resp.json()["items"])