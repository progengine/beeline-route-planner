"""Базовый план: first-fit в порядке входных заявок (раздел 2.3 — baseline)."""

from __future__ import annotations

from .explain import explain_assignment
from .models import (
    Engineer,
    EngineerRoute,
    PlanMetrics,
    PlanResult,
    Request,
    UnassignedReason,
    UnassignedRequest,
)
from .simulate import hard_constraints, sim_to_route_stops, simulate_route


def plan_greedy(engineers: list[Engineer], requests: list[Request]) -> PlanResult:
    """
    Для каждой заявки (в порядке списка) берём первого инженера,
    у которого маршрут остаётся допустимым после добавления в конец.
    """
    # engineer_id -> list[Request]
    sequences: dict[str, list[Request]] = {e.id: [] for e in engineers}
    eng_map = {e.id: e for e in engineers}
    unassigned: list[UnassignedRequest] = []
    explanations: dict[str, str] = {}

    # Срочные раньше
    ordered = sorted(
        requests,
        key=lambda r: (0 if r.priority.value == "urgent" else 1, r.window_start),
    )

    for req in ordered:
        placed = False
        last_fail: tuple[UnassignedReason, str] | None = None

        for eng in engineers:
            ok, reason, detail = hard_constraints(eng, req)
            if not ok:
                last_fail = (reason or UnassignedReason.MISSING_REQUIRED_SKILL, detail)
                continue

            trial = sequences[eng.id] + [req]
            sim = simulate_route(eng, trial)
            if not sim.feasible:
                last_fail = (
                    sim.fail_reason or UnassignedReason.DOES_NOT_FIT_TIME_WINDOW_OR_SHIFT,
                    sim.fail_detail or "не влезает в маршрут",
                )
                continue

            sequences[eng.id] = trial
            # индекс стопа = последний
            explanations[req.id] = explain_assignment(req, eng, sim, len(sim.stops) - 1)
            placed = True
            break

        if not placed:
            reason, detail = last_fail or (
                UnassignedReason.NO_AVAILABLE_ENGINEER_AT_TIME,
                "Нет свободного инженера с подходящим навыком/окном",
            )
            unassigned.append(
                UnassignedRequest(
                    request_id=req.id,
                    reason=reason,
                    explanation=detail,
                )
            )

    routes: list[EngineerRoute] = []
    dist_by: dict[str, float] = {}
    total = 0.0
    used = 0

    for eng in engineers:
        seq = sequences[eng.id]
        if not seq:
            continue
        sim = simulate_route(eng, seq)
        if not sim.feasible:
            # не должно случаться после проверки выше
            continue
        used += 1
        km = round(sim.total_distance_km, 3)
        dist_by[eng.id] = km
        total += km
        routes.append(
            EngineerRoute(
                engineer_id=eng.id,
                stops=sim_to_route_stops(sim),
                total_distance_km=km,
            )
        )

    return PlanResult(
        routes=routes,
        unassigned=unassigned,
        metrics=PlanMetrics(
            engineers_used=used,
            distance_by_engineer_km=dist_by,
            total_distance_km=round(total, 3),
        ),
        explanations=explanations,
    )
