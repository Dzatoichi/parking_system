from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.parkings import ParkingBase
from src.models.cameras import Cameras
from src.models.spots import Spot
from src.models.status.spot_status import SpotStatus
from src.models.system_events import SystemEvent
from src.models.tracking import Tracking
from src.models.vehicles import Vehicles
from src.schemas import (
    AnalyticsOverview,
    HourlyTrafficPoint,
    WeeklyOccupancyPoint,
    DurationBucket,
    RecentEvent,
    MiniSpot,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_event_time(value: datetime) -> str:
    return _as_utc(value).astimezone().strftime("%H:%M")


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_overview(self, parking_id: int) -> AnalyticsOverview:
        parking = await self._session.scalar(
            select(ParkingBase).where(ParkingBase.id == parking_id)
        )
        if parking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Парковка с id={parking_id} не найдена",
            )

        spots = (
            await self._session.execute(
                select(Spot).where(Spot.parking_id == parking_id).order_by(Spot.id)
            )
        ).scalars().all()

        free_spots = len([s for s in spots if s.spot_status == SpotStatus.FREE])
        occupied_spots = len([s for s in spots if s.spot_status == SpotStatus.OCCUPIED])
        total_spots = len(spots)
        occupancy_rate = (occupied_spots / total_spots) if total_spots else 0.0

        now = datetime.now(tz=timezone.utc)
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_week = start_today - timedelta(days=6)

        tracking_rows = (
            await self._session.execute(
                select(
                    Tracking.id,
                    Tracking.vehicle_id,
                    Tracking.spot_id,
                    Tracking.event_type,
                    Tracking.timestamp,
                    Vehicles.plate_number,
                )
                .join(Vehicles, Vehicles.id == Tracking.vehicle_id)
                .join(Cameras, Cameras.id == Tracking.camera_id)
                .where(
                    Cameras.parking_id == parking_id,
                    Tracking.timestamp >= start_week,
                )
                .order_by(Tracking.timestamp.desc())
            )
        ).all()

        entries_today = sum(
            1
            for row in tracking_rows
            if row.event_type == "enter" and _as_utc(row.timestamp) >= start_today
        )
        exits_today = sum(
            1
            for row in tracking_rows
            if row.event_type == "exit" and _as_utc(row.timestamp) >= start_today
        )

        current_vehicles = int(
            (
                await self._session.scalar(
                    select(func.count(Vehicles.id)).where(Vehicles.is_inside.is_(True))
                )
            )
            or 0
        )
        unique_visitors_week = len({row.vehicle_id for row in tracking_rows})

        hourly_counter: dict[int, int] = defaultdict(int)
        for row in tracking_rows:
            row_ts = _as_utc(row.timestamp)
            if row_ts >= start_today and row.event_type in {"enter", "park"}:
                hourly_counter[row_ts.hour] += 1
        hourly_traffic = [
            HourlyTrafficPoint(hour=f"{hour:02d}:00", vehicles=hourly_counter.get(hour, 0))
            for hour in range(24)
        ]
        peak_hour_num = max(range(24), key=lambda h: hourly_counter.get(h, 0))
        peak_hour = f"{peak_hour_num:02d}:00"

        weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        week_daily_vehicles: dict[int, set[int]] = {i: set() for i in range(7)}
        for row in tracking_rows:
            row_ts = _as_utc(row.timestamp)
            if row.event_type in {"enter", "park"} and row_ts >= start_week:
                week_daily_vehicles[row_ts.weekday()].add(row.vehicle_id)
        weekly_occupancy = [
            WeeklyOccupancyPoint(
                day=weekday_names[d],
                occupancy=round(
                    (len(week_daily_vehicles[d]) / max(total_spots, 1)) * 100,
                    2,
                ),
            )
            for d in range(7)
        ]
        peak_occupancy_percent = max((w.occupancy for w in weekly_occupancy), default=0.0)

        # Простейшая оценка длительности сессий: enter -> exit по vehicle_id.
        events_by_vehicle: dict[int, list] = defaultdict(list)
        for row in tracking_rows:
            events_by_vehicle[row.vehicle_id].append(row)
        durations_minutes: list[float] = []
        for _, rows in events_by_vehicle.items():
            enter_ts = None
            for row in sorted(rows, key=lambda r: _as_utc(r.timestamp)):
                row_ts = _as_utc(row.timestamp)
                if row.event_type == "enter":
                    enter_ts = row_ts
                elif row.event_type == "exit" and enter_ts is not None:
                    duration = (row_ts - enter_ts).total_seconds() / 60
                    if duration > 0:
                        durations_minutes.append(duration)
                    enter_ts = None

        avg_duration = round(
            sum(durations_minutes) / len(durations_minutes), 1
        ) if durations_minutes else 0.0

        buckets = {"< 1 часа": 0, "1-3 часа": 0, "3-6 часов": 0, "> 6 часов": 0}
        for minutes in durations_minutes:
            if minutes < 60:
                buckets["< 1 часа"] += 1
            elif minutes < 180:
                buckets["1-3 часа"] += 1
            elif minutes < 360:
                buckets["3-6 часов"] += 1
            else:
                buckets["> 6 часов"] += 1
        total_durations = sum(buckets.values()) or 1
        duration_distribution = [
            DurationBucket(name="< 1 часа", value=round(buckets["< 1 часа"] * 100 / total_durations, 2), color="#16a34a"),
            DurationBucket(name="1-3 часа", value=round(buckets["1-3 часа"] * 100 / total_durations, 2), color="#2563eb"),
            DurationBucket(name="3-6 часов", value=round(buckets["3-6 часов"] * 100 / total_durations, 2), color="#f59e0b"),
            DurationBucket(name="> 6 часов", value=round(buckets["> 6 часов"] * 100 / total_durations, 2), color="#dc2626"),
        ]

        action_map = {
            "enter": "Въезд на парковку",
            "exit": "Выезд с парковки",
            "park": "Авто припарковано",
            "leave_spot": "Авто покинуло место",
            "pass": "Транзит через парковку",
        }
        system_event_rows = (
            await self._session.execute(
                select(SystemEvent)
                .where(
                    SystemEvent.parking_id == parking_id,
                    SystemEvent.created_at >= start_week,
                )
                .order_by(SystemEvent.created_at.desc(), SystemEvent.id.desc())
                .limit(7)
            )
        ).scalars().all()

        tracking_recent_events = [
            RecentEvent(
                type=row.event_type,
                plate=row.plate_number,
                time=_format_event_time(row.timestamp),
                action=action_map.get(row.event_type, row.event_type),
            )
            for row in tracking_rows[:7]
        ]
        system_recent_events = [
            RecentEvent(
                type=event.event_type,
                plate=f"{event.entity_type} #{event.entity_id}",
                time=_format_event_time(event.created_at),
                action=event.message,
            )
            for event in system_event_rows
        ]
        recent_events = [
            event
            for _, event in sorted(
                [
                    *(
                        (_as_utc(row.timestamp), event)
                        for row, event in zip(tracking_rows[:7], tracking_recent_events)
                    ),
                    *(
                        (_as_utc(row.created_at), event)
                        for row, event in zip(system_event_rows, system_recent_events)
                    ),
                ],
                key=lambda item: item[0].timestamp(),
                reverse=True,
            )[:7]
        ]

        mini_spots = [
            MiniSpot(
                id=spot.id,
                status="free" if spot.spot_status == SpotStatus.FREE else "occupied",
                plate=next(
                    (
                        row.plate_number
                        for row in tracking_rows
                        if row.vehicle_id == spot.current_vehicle_id
                    ),
                    None,
                ),
            )
            for spot in spots[:15]
        ]

        return AnalyticsOverview(
            parking_id=parking_id,
            total_spots=total_spots,
            free_spots=free_spots,
            occupied_spots=occupied_spots,
            occupancy_rate=round(occupancy_rate, 4),
            avg_duration_minutes=avg_duration,
            peak_occupancy_percent=peak_occupancy_percent,
            unique_visitors_week=unique_visitors_week,
            total_entries_today=entries_today,
            total_exits_today=exits_today,
            current_vehicles=current_vehicles,
            peak_hour=peak_hour,
            hourly_traffic=hourly_traffic,
            weekly_occupancy=weekly_occupancy,
            duration_distribution=duration_distribution,
            recent_events=recent_events,
            mini_spots=mini_spots,
        )
