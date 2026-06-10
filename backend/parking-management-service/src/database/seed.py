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


SERGEY_TEST_PARKING_NAME = "Парковка Сергея 5005"

SERGEY_TEST_SPOTS = [
    (
        "SG-5005-1",
        {"points": [[120, 120], [420, 120], [420, 280], [120, 280]], "center_x": 270, "center_y": 200},
    ),
    (
        "SG-5005-2",
        {"points": [[120, 300], [420, 300], [420, 460], [120, 460]], "center_x": 270, "center_y": 380},
    ),
    (
        "SG-5005-3",
        {"points": [[120, 480], [420, 480], [420, 640], [120, 640]], "center_x": 270, "center_y": 560},
    ),
]


async def _ensure_sergey_test_data(session) -> None:
    parking = await session.scalar(
        select(ParkingBase).where(ParkingBase.name == SERGEY_TEST_PARKING_NAME)
    )
    if parking is None:
        parking = ParkingBase(
            name=SERGEY_TEST_PARKING_NAME,
            address="Тестовые данные Сергея",
            total_spots=3,
            available_spots=3,
            coordinates={"lat": 0, "lng": 0},
            boundaries={"points": [[0, 0], [500, 0], [500, 265], [0, 265]]},
            is_active=True,
            settings={"source": "sergey_dump"},
        )
        session.add(parking)
        await session.flush()

    for spot_number, coordinates in SERGEY_TEST_SPOTS:
        spot = await session.scalar(
            select(Spot).where(
                Spot.parking_id == parking.id,
                Spot.spot_number == spot_number,
            )
        )
        if spot is None:
            session.add(
                Spot(
                    spot_number=spot_number,
                    spot_type=SpotType.STANDARD,
                    spot_status=SpotStatus.FREE,
                    spot_coordinates=coordinates,
                    occupied_since=None,
                    current_vehicle_id=None,
                    parking_id=parking.id,
                )
            )
        else:
            spot.spot_status = SpotStatus.FREE
            spot.spot_coordinates = coordinates
            spot.occupied_since = None
            spot.current_vehicle_id = None

    parking.total_spots = 3
    parking.available_spots = 3


async def seed_demo_data() -> None:
    demo_owner_id = 1

    async with db_helper.async_session_maker() as session:
        existing_count = await session.scalar(select(func.count(ParkingBase.id)))
        if existing_count and existing_count > 0:
            await _ensure_sergey_test_data(session)
            await session.commit()
            return

        parking = ParkingBase(
            name="MVP Парковка Центр",
            address="ул. Примерная, 10",
            total_spots=48,
            available_spots=0,
            coordinates={"lat": 55.751244, "lng": 37.618423},
            boundaries={"points": [[0, 0], [1200, 0], [1200, 700], [0, 700]]},
            is_active=True,
            settings={"timezone": "Europe/Moscow"},
        )
        session.add(parking)
        await session.flush()

        now_utc_naive = datetime.utcnow()
        inside_plates = [
            "A123BC77", "M456OP77", "K890TT77", "P111AA77", "B222BB77", "C333CC77",
            "D444DD77", "E555EE77", "F666FF77", "G777GG77", "H888HH77", "J999JJ77",
        ]
        outside_plates = [
            "L101LL77", "N202NN77", "R303RR77", "S404SS77", "T505TT77", "U606UU77",
            "V707VV77", "W808WW77",
        ]
        blocked_plates = ["X909XX77", "Y010YY77", "Z121ZZ77"]

        vehicles: list[Vehicles] = []
        for idx, plate in enumerate(inside_plates):
            vehicles.append(
                Vehicles(
                    plate_number=plate,
                    is_inside=True,
                    is_blocked=False,
                    last_seen=now_utc_naive - timedelta(minutes=idx * 4 + 3),
                    owner_id=demo_owner_id,
                )
            )
        for idx, plate in enumerate(outside_plates):
            vehicles.append(
                Vehicles(
                    plate_number=plate,
                    is_inside=False,
                    is_blocked=False,
                    last_seen=now_utc_naive - timedelta(hours=idx + 2),
                    owner_id=demo_owner_id,
                )
            )
        for idx, plate in enumerate(blocked_plates):
            vehicles.append(
                Vehicles(
                    plate_number=plate,
                    is_inside=False,
                    is_blocked=True,
                    last_seen=now_utc_naive - timedelta(days=idx + 1, hours=2),
                    owner_id=demo_owner_id,
                )
            )
        session.add_all(vehicles)
        await session.flush()

        spots: list[Spot] = []
        inside_vehicle_ids = [v.id for v in vehicles if v.is_inside]
        inside_pointer = 0
        for i in range(1, 49):
            status = SpotStatus.FREE
            current_vehicle_id = None
            if i <= len(inside_vehicle_ids):
                status = SpotStatus.OCCUPIED
                current_vehicle_id = inside_vehicle_ids[inside_pointer]
                inside_pointer += 1

            row = (i - 1) // 8
            col = (i - 1) % 8
            x = col * 110
            y = row * 100

            spots.append(
                Spot(
                    spot_number=f"{chr(65 + row)}-{col + 1:02d}",
                    spot_type=SpotType.DISABLED if i in (8, 16, 24, 32, 40, 48) else SpotType.STANDARD,
                    spot_status=status,
                    spot_coordinates={
                        "points": [[x, y], [x + 90, y], [x + 90, y + 58], [x, y + 58]],
                        "center_x": x + 45,
                        "center_y": y + 29,
                    },
                    occupied_since=datetime.now(tz=timezone.utc) - timedelta(minutes=(i * 6) % 180)
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
                monitored_spot_ids=[s.id for s in spots[:16]],
                parking_id=parking.id,
            ),
            Cameras(
                rtsp_url="rtsp://demo:demo@192.168.1.22:554/stream1",
                status=CameraStatus.ACTIVE,
                position_x=700.0,
                position_y=420.0,
                is_calibrated=True,
                monitored_spot_ids=[s.id for s in spots[16:32]],
                parking_id=parking.id,
            ),
            Cameras(
                rtsp_url="rtsp://demo:demo@192.168.1.23:554/stream1",
                status=CameraStatus.ACTIVE,
                position_x=980.0,
                position_y=580.0,
                is_calibrated=True,
                monitored_spot_ids=[s.id for s in spots[32:]],
                parking_id=parking.id,
            ),
        ]
        session.add_all(cameras)
        await session.flush()

        for idx, vehicle in enumerate(vehicles):
            vehicle.last_camera_id = cameras[idx % len(cameras)].id

        now_utc = datetime.now(tz=timezone.utc)
        tracking_events: list[Tracking] = []
        for idx, vehicle in enumerate(vehicles):
            cam_id = cameras[idx % len(cameras)].id
            enter_ts = now_utc - timedelta(minutes=(idx * 25 + 60))
            tracking_events.append(
                Tracking(
                    vehicle_id=vehicle.id,
                    camera_id=cam_id,
                    spot_id=None,
                    timestamp=enter_ts,
                    event_type="enter",
                    bbox={"x1": 110, "y1": 110, "x2": 210, "y2": 220, "confidence": 0.93},
                )
            )
            vehicle_spot = next((s for s in spots if s.current_vehicle_id == vehicle.id), None)
            if vehicle.is_inside and vehicle_spot:
                tracking_events.append(
                    Tracking(
                        vehicle_id=vehicle.id,
                        camera_id=cam_id,
                        spot_id=vehicle_spot.id,
                        timestamp=enter_ts + timedelta(minutes=5),
                        event_type="park",
                        bbox={"x1": 190, "y1": 145, "x2": 280, "y2": 248, "confidence": 0.95},
                    )
                )
            else:
                spot_for_history = spots[(idx * 3) % len(spots)]
                tracking_events.append(
                    Tracking(
                        vehicle_id=vehicle.id,
                        camera_id=cam_id,
                        spot_id=spot_for_history.id,
                        timestamp=enter_ts + timedelta(minutes=8),
                        event_type="park",
                        bbox={"x1": 180, "y1": 150, "x2": 290, "y2": 250, "confidence": 0.92},
                    )
                )
                tracking_events.append(
                    Tracking(
                        vehicle_id=vehicle.id,
                        camera_id=cam_id,
                        spot_id=spot_for_history.id,
                        timestamp=enter_ts + timedelta(minutes=70),
                        event_type="leave_spot",
                        bbox={"x1": 180, "y1": 152, "x2": 285, "y2": 248, "confidence": 0.89},
                    )
                )
                tracking_events.append(
                    Tracking(
                        vehicle_id=vehicle.id,
                        camera_id=cam_id,
                        spot_id=None,
                        timestamp=enter_ts + timedelta(minutes=82),
                        event_type="exit",
                        bbox={"x1": 120, "y1": 120, "x2": 215, "y2": 225, "confidence": 0.90},
                    )
                )

        session.add_all(tracking_events)
        parking.available_spots = len([s for s in spots if s.spot_status == SpotStatus.FREE])
        await _ensure_sergey_test_data(session)
        await session.commit()
