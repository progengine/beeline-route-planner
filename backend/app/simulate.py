"""Симуляция маршрута инженера с проверкой жёстких ограничений."""

from __future__ import annotations

from dataclasses import dataclass, field

from .geo import road_distance_km, travel_time_minutes
from .models import (
    Coordinates,
    Engineer,
    Request,
    RouteStop,
    UnassignedReason,
)
from .time_utils import add_minutes, time_to_minutes


@dataclass
class SimStop:
    request: Request
    arrival: int  # minutes from midnight
    start: int
    end: int
    travel_km: float
    travel_min: int


@dataclass
class SimResult:
    feasible: bool
    stops: list[SimStop] = field(default_factory=list)
    total_distance_km: float = 0.0
    fail_reason: UnassignedReason | None = None
    fail_detail: str = ""


def hard_constraints(engineer: Engineer, req: Request) -> tuple[bool, UnassignedReason | None, str]:
    """Жёсткие ограничения навыка и транспорта (без времени)."""
    if req.required_skill not in engineer.skills:
        return (
            False,
            UnassignedReason.MISSING_REQUIRED_SKILL,
            f"Нет навыка «{req.required_skill.value}» у инженера {engineer.id}",
        )
    if req.required_vehicle_type is not None and req.required_vehicle_type != engineer.vehicle_type:
        return (
            False,
            UnassignedReason.NO_ENGINEER_WITH_REQUIRED_VEHICLE,
            f"Нужен транспорт {req.required_vehicle_type.value}, у инженера {engineer.vehicle_type.value}",
        )
    return True, None, ""


def simulate_route(
    engineer: Engineer,
    ordered_requests: list[Request],
    req_by_id: dict[str, Request] | None = None,
) -> SimResult:
    """
    Проигрывает маршрут: база → заявки по порядку.
    Проверяет окна и конец смены.
    """
    if not ordered_requests:
        return SimResult(feasible=True)

    for req in ordered_requests:
        ok, reason, detail = hard_constraints(engineer, req)
        if not ok:
            return SimResult(feasible=False, fail_reason=reason, fail_detail=detail)

    shift_start = time_to_minutes(engineer.shift_start)
    shift_end = time_to_minutes(engineer.shift_end)
    cursor = shift_start
    pos = engineer.start_coordinates
    stops: list[SimStop] = []
    total_km = 0.0

    for req in ordered_requests:
        if req.coordinates is None:
            return SimResult(
                feasible=False,
                fail_reason=UnassignedReason.DOES_NOT_FIT_TIME_WINDOW_OR_SHIFT,
                fail_detail=f"У заявки {req.id} нет координат",
            )

        travel_min = travel_time_minutes(pos, req.coordinates, engineer.vehicle_type)
        travel_km = road_distance_km(pos, req.coordinates, engineer.vehicle_type)
        arrival = cursor + travel_min
        window_start = time_to_minutes(req.window_start)
        window_end = time_to_minutes(req.window_end)
        start = max(arrival, window_start)
        end = start + req.duration_minutes

        if start > window_end:
            return SimResult(
                feasible=False,
                fail_reason=UnassignedReason.DOES_NOT_FIT_TIME_WINDOW_OR_SHIFT,
                fail_detail=(
                    f"Заявка {req.id}: прибытие/старт {start // 60:02d}:{start % 60:02d} "
                    f"после окна до {req.window_end.strftime('%H:%M')}"
                ),
            )
        if end > shift_end:
            return SimResult(
                feasible=False,
                fail_reason=UnassignedReason.DOES_NOT_FIT_TIME_WINDOW_OR_SHIFT,
                fail_detail=(
                    f"Заявка {req.id}: окончание работ {end // 60:02d}:{end % 60:02d} "
                    f"после смены {engineer.shift_end.strftime('%H:%M')}"
                ),
            )

        stops.append(
            SimStop(
                request=req,
                arrival=arrival,
                start=start,
                end=end,
                travel_km=travel_km,
                travel_min=travel_min,
            )
        )
        total_km += travel_km
        cursor = end
        pos = req.coordinates

    return SimResult(feasible=True, stops=stops, total_distance_km=total_km)


def sim_to_route_stops(sim: SimResult) -> list[RouteStop]:
    from .time_utils import minutes_to_time

    return [
        RouteStop(
            request_id=s.request.id,
            planned_arrival=minutes_to_time(s.arrival),
            planned_start=minutes_to_time(s.start),
            planned_end=minutes_to_time(s.end),
            travel_distance_km=round(s.travel_km, 3),
            travel_time_minutes=s.travel_min,
        )
        for s in sim.stops
    ]
