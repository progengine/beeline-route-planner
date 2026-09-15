"""DTO для HTTP API (вход/выход)."""

from __future__ import annotations

from datetime import time
from typing import Any, Optional

from pydantic import BaseModel, Field

from .models import (
    Coordinates,
    Engineer,
    EventType,
    PlanResult,
    Priority,
    Request,
    ReplanEvent,
    Skill,
    VehicleType,
)


class PlanRequestBody(BaseModel):
    engineers: list[Engineer]
    requests: list[Request]
    mode: str = Field(default="optimized", description="greedy | optimized")


class ReplanRequestBody(BaseModel):
    engineers: list[Engineer]
    requests: list[Request]
    event: ReplanEvent
    previous_plan: Optional[PlanResult] = None
    mode: str = Field(default="optimized")


class CompareResponse(BaseModel):
    baseline: PlanResult
    optimized: PlanResult
    delta_engineers: int
    delta_distance_km: float


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


class ScenarioResponse(BaseModel):
    engineers: list[Engineer]
    requests: list[Request]
    meta: dict[str, Any] = Field(default_factory=dict)
