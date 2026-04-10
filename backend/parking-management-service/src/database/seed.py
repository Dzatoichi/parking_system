from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from src.database.base import db_helper
from src.models.cameras import Cameras
from src.models.parkings import ParkingBase
from src.models.spots import Spot
from src.models.status.camera_status import CameraStatus
from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType
from src.models.tracking import Tracking
from src.models.vehicles import Vehicles


async def seed_demo_data() -> None:
    """
    Заполняет БД демо-данными для MVP, если таблицы пустые.
    """
    async with db_helper.async_session_maker() as session:
        existing_count = await session.scalar(select(func.count(ParkingBase.id)))
        if existing_count and existing_count > 0:
            return

        parking = ParkingBase(
            name="MVP Парковка Центр",
            address="ул. Примерная, 10",
            total_spots=12,
            available_spots=4,
            coordinates={"lat": 55.751244, "lng": 37.618423},
            boundaries={"points": [[0, 0], [1200, 0], [1200, 700], [0, 700]]},
            is_active=True,
            settings={"timezone": "Europe/Moscow"},
        )
        session.add(parking)
        await session.flush()

        # vehicles.last_seen в схеме: TIMESTAMP WITHOUT TIME ZONE,
        # поэтому передаем naive datetime (UTC) без tzinfo.
        now_utc_naive = datetime.utcnow()

        car_1 = Vehicles(
            plate_number="A123BC77",
            is_inside=True,
            is_blocked=False,
            last_seen=now_utc_naive - timedelta(minutes=12),
        )
        car_2 = Vehicles(
            plate_number="M456OP77",
            is_inside=True,
            is_blocked=False,
            last_seen=now_utc_naive - timedelta(minutes=40),
        )
        car_3 = Vehicles(
            plate_number="K890TT77",
            is_inside=True,
            is_blocked=False,
            last_seen=now_utc_naive - timedelta(minutes=5),
        )
        car_4 = Vehicles(
            plate_number="E111KO77",
            is_inside=False,
            is_blocked=False,
            last_seen=now_utc_naive - timedelta(hours=3),
        )
        car_5 = Vehicles(
            plate_number="T777TT77",
            is_inside=False,
            is_blocked=True,
            last_seen=now_utc_naive - timedelta(days=1, hours=2),
        )
        session.add_all([car_1, car_2, car_3, car_4, car_5])
        await session.flush()

        spots: list[Spot] = []
        for i in range(1, 13):
            status = SpotStatus.FREE
            current_vehicle_id = None
            if i in (2, 5, 8):
                status = SpotStatus.OCCUPIED
            if i == 2:
                current_vehicle_id = car_1.id
            elif i == 5:
                current_vehicle_id = car_2.id
            elif i == 8:
                current_vehicle_id = car_3.id

            x = ((i - 1) % 4) * 100
            y = ((i - 1) // 4) * 120

            spots.append(
                Spot(
                    spot_number=f"A-{i:02d}",
                    spot_type=SpotType.STANDARD if i != 12 else SpotType.DISABLED,
                    spot_status=status,
                    spot_coordinates={
                        "points": [[x, y], [x + 80, y], [x + 80, y + 60], [x, y + 60]],
                        "center_x": x + 40,
                        "center_y": y + 30,
                    },
                    occupied_since=datetime.now(tz=timezone.utc) - timedelta(minutes=30)
                    if status == SpotStatus.OCCUPIED
                    else None,
                    current_vehicle_id=current_vehicle_id,
                    parking_id=parking.id,
                )
            )

        session.add_all(spots)
        await session.flush()

        cameras = [
            Cameras(
                rtsp_url="rtsp://demo:demo@192.168.1.21:554/stream1",
                status=CameraStatus.ACTIVE,
                position_x=250.0,
                position_y=180.0,
                is_calibrated=True,
                monitored_spot_ids=[spots[0].id, spots[1].id, spots[2].id, spots[3].id],
                parking_id=parking.id,
            ),
            Cameras(
                rtsp_url="rtsp://demo:demo@192.168.1.22:554/stream1",
                status=CameraStatus.ACTIVE,
                position_x=700.0,
                position_y=420.0,
                is_calibrated=True,
                monitored_spot_ids=[spots[4].id, spots[5].id, spots[6].id, spots[7].id],
                parking_id=parking.id,
            ),
        ]
        session.add_all(cameras)
        await session.flush()

        car_1.last_camera_id = cameras[0].id
        car_2.last_camera_id = cameras[1].id
        car_3.last_camera_id = cameras[1].id
        car_4.last_camera_id = cameras[0].id

        now_utc = datetime.now(tz=timezone.utc)
        tracking_events = [
            Tracking(
                vehicle_id=car_1.id,
                camera_id=cameras[0].id,
                spot_id=None,
                timestamp=now_utc - timedelta(minutes=55),
                event_type="enter",
                bbox={"x1": 110, "y1": 120, "x2": 200, "y2": 220, "confidence": 0.96},
            ),
            Tracking(
                vehicle_id=car_1.id,
                camera_id=cameras[0].id,
                spot_id=spots[1].id,
                timestamp=now_utc - timedelta(minutes=50),
                event_type="park",
                bbox={"x1": 210, "y1": 170, "x2": 290, "y2": 260, "confidence": 0.94},
            ),
            Tracking(
                vehicle_id=car_2.id,
                camera_id=cameras[1].id,
                spot_id=None,
                timestamp=now_utc - timedelta(hours=1, minutes=45),
                event_type="enter",
                bbox={"x1": 120, "y1": 130, "x2": 220, "y2": 240, "confidence": 0.93},
            ),
            Tracking(
                vehicle_id=car_2.id,
                camera_id=cameras[1].id,
                spot_id=spots[4].id,
                timestamp=now_utc - timedelta(hours=1, minutes=40),
                event_type="park",
                bbox={"x1": 220, "y1": 160, "x2": 300, "y2": 250, "confidence": 0.95},
            ),
            Tracking(
                vehicle_id=car_3.id,
                camera_id=cameras[1].id,
                spot_id=None,
                timestamp=now_utc - timedelta(minutes=25),
                event_type="enter",
                bbox={"x1": 90, "y1": 110, "x2": 180, "y2": 215, "confidence": 0.91},
            ),
            Tracking(
                vehicle_id=car_3.id,
                camera_id=cameras[1].id,
                spot_id=spots[7].id,
                timestamp=now_utc - timedelta(minutes=21),
                event_type="park",
                bbox={"x1": 180, "y1": 150, "x2": 280, "y2": 240, "confidence": 0.92},
            ),
            Tracking(
                vehicle_id=car_4.id,
                camera_id=cameras[0].id,
                spot_id=None,
                timestamp=now_utc - timedelta(hours=6),
                event_type="enter",
                bbox={"x1": 130, "y1": 140, "x2": 225, "y2": 250, "confidence": 0.90},
            ),
            Tracking(
                vehicle_id=car_4.id,
                camera_id=cameras[0].id,
                spot_id=spots[0].id,
                timestamp=now_utc - timedelta(hours=5, minutes=50),
                event_type="park",
                bbox={"x1": 200, "y1": 155, "x2": 290, "y2": 250, "confidence": 0.93},
            ),
            Tracking(
                vehicle_id=car_4.id,
                camera_id=cameras[0].id,
                spot_id=spots[0].id,
                timestamp=now_utc - timedelta(hours=3, minutes=15),
                event_type="leave_spot",
                bbox={"x1": 210, "y1": 160, "x2": 300, "y2": 255, "confidence": 0.89},
            ),
            Tracking(
                vehicle_id=car_4.id,
                camera_id=cameras[0].id,
                spot_id=None,
                timestamp=now_utc - timedelta(hours=3),
                event_type="exit",
                bbox={"x1": 100, "y1": 120, "x2": 190, "y2": 220, "confidence": 0.90},
            ),
        ]
        session.add_all(tracking_events)

        parking.available_spots = 9
        await session.commit()
