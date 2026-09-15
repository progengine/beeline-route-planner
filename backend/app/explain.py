"""Человекочитаемые объяснения назначений (раздел 2.4.2 ТЗ)."""

from __future__ import annotations

from .labels import skill_ru, vehicle_ru
from .models import Engineer, PlanResult, Request, UnassignedRequest
from .simulate import SimResult


def explain_assignment(
    req: Request,
    engineer: Engineer,
    sim: SimResult,
    stop_index: int,
) -> str:
    skill = skill_ru(req.required_skill)
    vehicle = vehicle_ru(engineer.vehicle_type)
    if stop_index < len(sim.stops):
        st = sim.stops[stop_index]
        start = f"{st.start // 60:02d}:{st.start % 60:02d}"
        travel = st.travel_min
        dist = st.travel_km
    else:
        start = "?"
        travel = 0
        dist = 0.0

    name = engineer.name or engineer.id
    parts = [
        f"Заявка {req.id} назначена инженеру «{name}».",
        f"Подходит по компетенции: «{skill}», транспорт: {vehicle}.",
        f"Окно клиента {req.window_start.strftime('%H:%M')}–{req.window_end.strftime('%H:%M')}, "
        f"план: выезд/старт работ около {start}, в пути ≈ {travel} мин ({dist:.1f} км по дороге).",
    ]
    if req.priority.value == "urgent":
        parts.append("Приоритет: срочная.")
    if req.required_vehicle_type:
        parts.append(f"Требование к ТС учтено: {vehicle_ru(req.required_vehicle_type)}.")
    return " ".join(parts)


def build_explanations(
    plan: PlanResult,
    engineers: list[Engineer],
    requests: list[Request],
) -> dict[str, str]:
    eng_map = {e.id: e for e in engineers}
    req_map = {r.id: r for r in requests}
    out = dict(plan.explanations)

    for route in plan.routes:
        eng = eng_map.get(route.engineer_id)
        if not eng:
            continue
        for stop in route.stops:
            rid = stop.request_id
            if rid in out:
                continue
            req = req_map.get(rid)
            if not req:
                continue
            out[rid] = (
                f"Заявка {rid} → «{eng.name or eng.id}»: "
                f"компетенция «{skill_ru(req.required_skill)}», "
                f"старт {stop.planned_start.strftime('%H:%M')}, "
                f"в пути {stop.travel_time_minutes} мин, "
                f"{stop.travel_distance_km:.1f} км."
            )

    for u in plan.unassigned:
        if u.request_id not in out:
            out[u.request_id] = u.explanation

    return out
