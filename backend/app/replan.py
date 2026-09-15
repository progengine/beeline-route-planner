"""Перепланирование по событиям (раздел 2.4 ТЗ)."""

from __future__ import annotations

from .models import (
    Engineer,
    EventType,
    PlanResult,
    ReplanEvent,
    Request,
)
from .optimized import plan_optimized


def apply_event(
    engineers: list[Engineer],
    requests: list[Request],
    previous: PlanResult | None,
    event: ReplanEvent,
    mode: str = "optimized",
) -> PlanResult:
    """
    Применяет событие и строит новый план.
    mode: 'optimized' | 'greedy'
    """
    from .greedy import plan_greedy

    engs = list(engineers)
    reqs = list(requests)

    if event.type == EventType.NEW_URGENT_REQUEST:
        assert event.new_request is not None
        nr = event.new_request
        # срочный приоритет
        if nr.priority.value != "urgent":
            nr = nr.model_copy(update={"priority": nr.priority.__class__("urgent")})
        # заменить или добавить
        reqs = [r for r in reqs if r.id != nr.id] + [nr]

    elif event.type == EventType.CANCEL_REQUEST:
        assert event.request_id
        reqs = [r for r in reqs if r.id != event.request_id]

    elif event.type == EventType.ENGINEER_UNAVAILABLE:
        assert event.engineer_id
        engs = [e for e in engs if e.id != event.engineer_id]

    if mode == "greedy":
        plan = plan_greedy(engs, reqs)
    else:
        plan = plan_optimized(engs, reqs)

    if previous is not None:
        plan.changed_request_ids = _diff_assignments(previous, plan)

    return plan


def _diff_assignments(old: PlanResult, new: PlanResult) -> list[str]:
    def map_assign(p: PlanResult) -> dict[str, str]:
        m: dict[str, str] = {}
        for route in p.routes:
            for stop in route.stops:
                m[stop.request_id] = route.engineer_id
        return m

    a, b = map_assign(old), map_assign(new)
    changed: list[str] = []
    for rid in set(a) | set(b):
        if a.get(rid) != b.get(rid):
            changed.append(rid)
    return sorted(changed)
