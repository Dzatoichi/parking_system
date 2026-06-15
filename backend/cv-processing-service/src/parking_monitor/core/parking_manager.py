# core/parking_spot_manager.py
import threading
import time
from typing import Dict, List, Optional
from datetime import datetime

from parking_monitor.db.repository import ParkingRepository
from parking_monitor.db.models import ParkingSpotState, SpotStatus


class ParkingSpotManager:
    def __init__(self, db_repo: ParkingRepository,
                 confirmation_seconds: float = 2.0,
                 absence_timeout_seconds=3.0,
                 fps_estimate: float = 10.0):
        self.db = db_repo
        self.confirmation_frames = int(confirmation_seconds * fps_estimate)
        self.lock = threading.RLock()

        # Состояние всех мест
        self.spots: Dict[int, ParkingSpotState] = {}

        self.absence_timeout_seconds = absence_timeout_seconds

        # Загрузка начального состояния из БД (будет переопределена после верификации)
        self._load_initial_from_db()

    def _load_initial_from_db(self):
        active_occupancies = self.db.get_current_occupancy()
        current_time = time.time()
        for occ in active_occupancies:
            # Если occupied_since есть в записи, используем его timestamp
            last_seen = occ.occupied_since.timestamp() if occ.occupied_since else current_time
            self.spots[occ.spot_id] = ParkingSpotState(
                spot_id=occ.spot_id,
                status=SpotStatus.PARKING_PENDING,
                vehicle_track_id=occ.vehicle_track_id,
                first_seen_time=None,
                last_seen_time=last_seen,
                consecutive_frames=0
            )


    def update_from_detection(
    self,
    spot_id: int,
    track_id: int,
    timestamp: float,
):
        with self.lock:
            if spot_id not in self.spots:
                self.spots[spot_id] = ParkingSpotState(
                    spot_id=spot_id,
                    status=SpotStatus.FREE,
                )

            state = self.spots[spot_id]

            # Место подтверждённо занято.
            # Новый track_id не означает освобождение места.
            if state.status == SpotStatus.PARKING_CONFIRMED:
                state.last_seen_time = timestamp

                if state.vehicle_track_id != track_id:
                    print(
                        f"Spot {spot_id}: track changed "
                        f"{state.vehicle_track_id} -> {track_id}, "
                        f"keeping spot occupied"
                    )
                    state.vehicle_track_id = track_id

                    # При необходимости синхронизируем только vehicle_track_id,
                    # но не переводим место в free.
                    self.db.update_current_spot(
                        spot_id=spot_id,
                        status="occupied",
                        vehicle_track_id=track_id,
                        parked_since=state.confirmed_time,
                    )

                return

            # Свободное место — начинаем подтверждение парковки.
            if state.status == SpotStatus.FREE:
                state.status = SpotStatus.PARKING_PENDING
                state.vehicle_track_id = track_id
                state.first_seen_time = timestamp
                state.last_seen_time = timestamp
                state.consecutive_frames = 1
                return

            # Место ожидает подтверждения.
            if state.status == SpotStatus.PARKING_PENDING:
                state.last_seen_time = timestamp

                if state.vehicle_track_id == track_id:
                    state.consecutive_frames += 1
                else:
                    # Не освобождаем место.
                    # Перезапускаем подтверждение для нового трека.
                    print(
                        f"Spot {spot_id}: pending track changed "
                        f"{state.vehicle_track_id} -> {track_id}"
                    )
                    state.vehicle_track_id = track_id
                    state.first_seen_time = timestamp
                    state.consecutive_frames = 1

                if state.consecutive_frames >= self.confirmation_frames:
                    self._confirm_parking(
                        spot_id,
                        state.vehicle_track_id,
                        timestamp,
                    )

    def update_from_absence(self, spot_id: int, timestamp: float):
        with self.lock:
            state = self.spots.get(spot_id)
            if not state:
                return
            if state.status in (SpotStatus.PARKING_CONFIRMED, SpotStatus.PARKING_PENDING):
                if state.last_seen_time is not None and (
                        timestamp - state.last_seen_time) > self.absence_timeout_seconds:
                    self._free_spot(
                        spot_id,
                        timestamp,
                        reason="absence_timeout",
                    )

    def _confirm_parking(self, spot_id: int, track_id: int, timestamp: float):
        with self.lock:
            state = self.spots[spot_id]
            state.status = SpotStatus.PARKING_CONFIRMED
            real_now = datetime.now()
            state.confirmed_time = real_now
            # Пишем в лог (уже есть)
            self.db.mark_spot_occupied(spot_id, track_id)
            # Обновляем таблицу текущего состояния
            self.db.update_current_spot(spot_id, 'occupied', track_id, state.confirmed_time)
            print(f"Spot {spot_id} confirmed occupied by vehicle {track_id}")

    def _free_spot(
        self,
        spot_id: int,
        timestamp: float,
        reason: str = "absence_timeout",
    ):
        state = self.spots[spot_id]

        previous_status = state.status
        previous_vehicle_id = state.vehicle_track_id
        last_seen_time = state.last_seen_time

        # В БД пишем free только для реально подтверждённой парковки.
        if previous_status == SpotStatus.PARKING_CONFIRMED:
            self.db.mark_spot_free(spot_id)
            self.db.update_current_spot(
                spot_id=spot_id,
                status="free",
                vehicle_track_id=None,
                parked_since=None,
            )

            print(
                f"Spot {spot_id} confirmed free: "
                f"vehicle={previous_vehicle_id}, "
                f"reason={reason}, "
                f"absence={timestamp - last_seen_time if last_seen_time is not None else None}"
            )
        else:
            print(
                f"Spot {spot_id} pending reset: "
                f"vehicle={previous_vehicle_id}, "
                f"reason={reason}"
            )

        state.status = SpotStatus.FREE
        state.vehicle_track_id = None
        state.first_seen_time = None
        state.last_seen_time = None
        state.consecutive_frames = 0
        state.confirmed_time = None

    def get_spot_status(self, spot_id: int) -> SpotStatus:
        with self.lock:
            return self.spots.get(spot_id, ParkingSpotState(spot_id)).status

    def get_all_statuses(self) -> Dict[int, SpotStatus]:
        with self.lock:
            return {sid: s.status for sid, s in self.spots.items()}

    def get_confirmed_parked_vehicles(self) -> Dict[int, int]:
        """Возвращает {spot_id: track_id} для подтверждённых парковок"""
        with self.lock:
            return {
                sid: s.vehicle_track_id
                for sid, s in self.spots.items()
                if s.status == SpotStatus.PARKING_CONFIRMED
            }
