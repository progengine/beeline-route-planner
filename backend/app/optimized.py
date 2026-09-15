"""
Оптимизированный план (ТЗ 2.3):
1) минимизировать число задействованных инженеров;
2) при равном штате — минимизировать суммарный пробег.
"""

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


def plan_optimized(engineers: list[Engineer], requests: list[Request]) -> PlanResult:
    sequences: dict[str, list[Request]] = {e.id: [] for e in engineers}
    unassigned: list[UnassignedRequest] = []
    explanations: dict[str, str] = {}
    eng_map = {e.id: e for e in engineers}

    ordered = sorted(
        requests,
        key=lambda r: (
            0 if r.priority.value == "urgent" else 1,
            r.window_start,
            -r.duration_minutes,
        ),
    )

    for req in ordered:
        best: tuple[float, str, list[Request]] | None = None
        last_fail: tuple[UnassignedReason, str] | None = None

        for eng in engineers:
            ok, reason, detail = hard_constraints(eng, req)
            if not ok:
                last_fail = (reason or UnassignedReason.MISSING_REQUIRED_SKILL, detail)
                continue

            current = sequences[eng.id]
            is_new = 1 if len(current) == 0 else 0

            for pos in range(len(current) + 1):
                trial = current[:pos] + [req] + current[pos:]
                sim = simulate_route(eng, trial)
                if not sim.feasible:
                    last_fail = (
                        sim.fail_reason
                        or UnassignedReason.DOES_NOT_FIT_TIME_WINDOW_OR_SHIFT,
                        sim.fail_detail or "не влезает в маршрут/окно/смену",
                    )
                    continue
                cost = is_new * 1000.0 + sim.total_distance_km
                if best is None or cost < best[0]:
                    best = (cost, eng.id, trial)

        if best is None:
            reason, detail = last_fail or (
                UnassignedReason.NO_AVAILABLE_ENGINEER_AT_TIME,
                "Нет допустимого назначения",
            )
            unassigned.append(
                UnassignedRequest(request_id=req.id, reason=reason, explanation=detail)
            )
            continue

        _, eid, trial = best
        sequences[eid] = trial

    sequences = _pack_routes(engineers, sequences)
    sequences = _two_opt_all(engineers, sequences)

    routes: list[EngineerRoute] = []
    dist_by: dict[str, float] = {}
    total = 0.0
    used = 0

    for eng in engineers:
        seq = sequences.get(eng.id) or []
        if not seq:
            continue
        sim = simulate_route(eng, seq)
        if not sim.feasible:
            for r in seq:
                unassigned.append(
                    UnassignedRequest(
                        request_id=r.id,
                        reason=UnassignedReason.DOES_NOT_FIT_TIME_WINDOW_OR_SHIFT,
                        explanation=sim.fail_detail or "маршрут недопустимый",
                    )
                )
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
        for i, st in enumerate(sim.stops):
            explanations[st.request.id] = explain_assignment(st.request, eng, sim, i)

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


def _pack_routes(
    engineers: list[Engineer],
    sequences: dict[str, list[Request]],
) -> dict[str, list[Request]]:
    """Пытается уменьшить число инженеров, перекладывая короткие маршруты."""
    seq = {k: list(v) for k, v in sequences.items()}
    eng_map = {e.id: e for e in engineers}

    # один проход по возрастанию размера маршрута
    occupied = sorted(
        [eid for eid, s in seq.items() if s],
        key=lambda eid: len(seq[eid]),
    )

    for src_id in occupied:
        src = list(seq.get(src_id) or [])
        if not src:
            continue
        trial = {k: list(v) for k, v in seq.items()}
        trial[src_id] = []
        ok_all = True
        for req in src:
            placed = False
            candidates = sorted(
                [e for e in engineers if e.id != src_id],
                key=lambda e: (0 if trial[e.id] else 1, len(trial[e.id])),
            )
            for eng in candidates:
                dst = trial[eng.id]
                best_pos = None
                best_km = 1e9
                for pos in range(len(dst) + 1):
                    candidate = dst[:pos] + [req] + dst[pos:]
                    sim = simulate_route(eng, candidate)
                    if sim.feasible and sim.total_distance_km < best_km:
                        best_km = sim.total_distance_km
                        best_pos = pos
                if best_pos is not None:
                    trial[eng.id] = dst[:best_pos] + [req] + dst[best_pos:]
                    placed = True
                    break
            if not placed:
                ok_all = False
                break
        if ok_all:
            seq = trial

    return seq


def _two_opt_all(
    engineers: list[Engineer],
    sequences: dict[str, list[Request]],
) -> dict[str, list[Request]]:
    """2-opt внутри каждого маршрута (одна волна)."""
    seq = {k: list(v) for k, v in sequences.items()}
    eng_map = {e.id: e for e in engineers}

    for eid, route in list(seq.items()):
        if len(route) < 3:
            continue
        improved = True
        while improved:
            improved = False
            n = len(route)
            best_route = route
            best_km = None
            sim0 = simulate_route(eng_map[eid], route)
            if not sim0.feasible:
                break
            best_km = sim0.total_distance_km
            for i in range(n - 1):
                for j in range(i + 2, n):
                    new_route = route[:i] + list(reversed(route[i : j + 1])) + route[j + 1 :]
                    sim = simulate_route(eng_map[eid], new_route)
                    if sim.feasible and sim.total_distance_km + 1e-9 < best_km:
                        best_km = sim.total_distance_km
                        best_route = new_route
                        improved = True
            route = best_route
            seq[eid] = route

    return seq
