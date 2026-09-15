"""
FastAPI — сервис планирования маршрутов «Билайн Бизнес».

Эндпоинты:
  GET  /health
  GET  /scenario/demo          — демо-день из JSON (с координатами)
  POST /plan                   — построить план (greedy | optimized)
  POST /plan/compare           — baseline + optimized + дельта метрик
  POST /replan                 — перепланирование по событию
"""

from __future__ import annotations

import json
from datetime import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .greedy import plan_greedy
from .models import (
    Coordinates,
    Engineer,
    PlanResult,
    Priority,
    Request,
    Skill,
    VehicleType,
)
from .optimized import plan_optimized
from .replan import apply_event
from .schemas import (
    CompareResponse,
    HealthResponse,
    PlanRequestBody,
    ReplanRequestBody,
    ScenarioResponse,
)

app = FastAPI(
    title="Beeline Business — Route Planner",
    description="Планирование маршрутов полевых инженеров (VRPTW heuristic)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEMO_JSON = DATA_DIR / "beeline-day-2026-08-17.json"


def _parse_hhmm(s: str) -> time:
    h, m = s.strip().split(":")
    return time(int(h), int(m))


def load_demo_scenario() -> tuple[list[Engineer], list[Request], dict[str, Any]]:
    """
    Приоритет источников:
    1) data/control_distribution.csv  (контрольное распределение Билайн)
    2) data/synthetic_requests.csv
    3) data/beeline-day-2026-08-17.json
    """
    from .csv_import import parse_csv_text

    control = DATA_DIR / "control_distribution.csv"
    synthetic = DATA_DIR / "synthetic_requests.csv"

    if control.exists():
        text_body = control.read_text(encoding="utf-8")
        requests, engineers, meta = parse_csv_text(text_body, only_active=True)
        meta["source_file"] = control.name
        return engineers, requests, meta

    if synthetic.exists():
        text_body = synthetic.read_text(encoding="utf-8")
        requests, engineers, meta = parse_csv_text(text_body, only_active=False)
        meta["source_file"] = synthetic.name
        return engineers, requests, meta

    if not DEMO_JSON.exists():
        raise HTTPException(status_code=404, detail="Нет CSV/JSON в data/")

    raw = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    meta = raw.get("meta") or {}
    meta["source_file"] = DEMO_JSON.name

    engineers = []
    for e in raw.get("engineers") or []:
        engineers.append(
            Engineer(
                id=e["id"],
                name=e.get("name"),
                start_coordinates=Coordinates(
                    lat=e["start_coordinates"]["lat"],
                    lon=e["start_coordinates"]["lon"],
                ),
                shift_start=_parse_hhmm(e["shift_start"]),
                shift_end=_parse_hhmm(e["shift_end"]),
                skills=[Skill(s) for s in e["skills"]],
                vehicle_type=VehicleType(e["vehicle_type"]),
            )
        )

    requests = []
    for r in raw.get("requests") or []:
        coords = r.get("coordinates")
        requests.append(
            Request(
                id=r["id"],
                address=r.get("address"),
                coordinates=Coordinates(lat=coords["lat"], lon=coords["lon"]) if coords else None,
                duration_minutes=int(r["duration_minutes"]),
                window_start=_parse_hhmm(r["window_start"]),
                window_end=_parse_hhmm(r["window_end"]),
                priority=Priority(r.get("priority", "normal")),
                required_skill=Skill(r["required_skill"]),
                required_vehicle_type=VehicleType(r["required_vehicle_type"])
                if r.get("required_vehicle_type")
                else None,
            )
        )

    return engineers, requests, meta


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/scenario/demo", response_model=ScenarioResponse)
def scenario_demo() -> ScenarioResponse:
    engineers, requests, meta = load_demo_scenario()
    return ScenarioResponse(engineers=engineers, requests=requests, meta=meta)


@app.post("/plan", response_model=PlanResult)
def plan(body: PlanRequestBody) -> PlanResult:
    if body.mode not in ("greedy", "optimized"):
        raise HTTPException(400, "mode должен быть greedy или optimized")
    if body.mode == "greedy":
        return plan_greedy(body.engineers, body.requests)
    return plan_optimized(body.engineers, body.requests)


@app.post("/plan/compare", response_model=CompareResponse)
def plan_compare(body: PlanRequestBody) -> CompareResponse:
    baseline = plan_greedy(body.engineers, body.requests)
    optimized = plan_optimized(body.engineers, body.requests)
    return CompareResponse(
        baseline=baseline,
        optimized=optimized,
        delta_engineers=baseline.metrics.engineers_used - optimized.metrics.engineers_used,
        delta_distance_km=round(
            baseline.metrics.total_distance_km - optimized.metrics.total_distance_km, 3
        ),
    )


@app.post("/replan", response_model=PlanResult)
def replan(body: ReplanRequestBody) -> PlanResult:
    if body.mode not in ("greedy", "optimized"):
        raise HTTPException(400, "mode должен быть greedy или optimized")
    return apply_event(
        body.engineers,
        body.requests,
        body.previous_plan,
        body.event,
        mode=body.mode,
    )




@app.post("/scenario/csv", response_model=ScenarioResponse)
async def scenario_from_csv(
    file: UploadFile = File(...),
    only_active: bool = True,
) -> ScenarioResponse:
    """Загрузка CSV (control или synthetic). Возвращает engineers + requests."""
    from .csv_import import parse_csv_text

    raw = await file.read()
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            text_body = raw.decode(enc)
            break
        except UnicodeDecodeError:
            text_body = None
    else:
        raise HTTPException(400, "Не удалось декодировать CSV (utf-8 / cp1251)")

    try:
        requests, engineers, meta = parse_csv_text(text_body, only_active=only_active)
    except Exception as e:
        raise HTTPException(400, f"Ошибка разбора CSV: {e}") from e

    if not requests:
        raise HTTPException(400, "После фильтра не осталось заявок")
    meta["filename"] = file.filename
    return ScenarioResponse(engineers=engineers, requests=requests, meta=meta)


@app.post("/plan/csv")
async def plan_from_csv(
    file: UploadFile = File(...),
    mode: str = "optimized",
    only_active: bool = True,
):
    """Загрузить CSV и сразу построить план."""
    from .csv_import import parse_csv_text

    if mode not in ("greedy", "optimized"):
        raise HTTPException(400, "mode: greedy | optimized")

    raw = await file.read()
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            text_body = raw.decode(enc)
            break
        except UnicodeDecodeError:
            text_body = None
    else:
        raise HTTPException(400, "Не удалось декодировать CSV")

    requests, engineers, meta = parse_csv_text(text_body, only_active=only_active)
    if mode == "greedy":
        plan = plan_greedy(engineers, requests)
    else:
        plan = plan_optimized(engineers, requests)
    return {"meta": meta, "plan": plan, "engineers": engineers, "requests": requests}


@app.post("/plan/csv/compare")
async def compare_from_csv(
    file: UploadFile = File(...),
    only_active: bool = True,
):
    """CSV → baseline + optimized."""
    from .csv_import import parse_csv_text

    raw = await file.read()
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            text_body = raw.decode(enc)
            break
        except UnicodeDecodeError:
            text_body = None
    else:
        raise HTTPException(400, "Не удалось декодировать CSV")

    requests, engineers, meta = parse_csv_text(text_body, only_active=only_active)
    baseline = plan_greedy(engineers, requests)
    optimized = plan_optimized(engineers, requests)
    return {
        "meta": meta,
        "baseline": baseline,
        "optimized": optimized,
        "delta_engineers": baseline.metrics.engineers_used - optimized.metrics.engineers_used,
        "delta_distance_km": round(
            baseline.metrics.total_distance_km - optimized.metrics.total_distance_km, 3
        ),
        "engineers": engineers,
        "requests": requests,
    }




@app.get("/geo/route")
def geo_route(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    vehicle: str = "car",
):
    """Геометрия маршрута по дорогам (OSRM) для отрисовки на карте."""
    from .geo import route_geometry
    from .models import Coordinates, VehicleType

    try:
        v = VehicleType(vehicle)
    except ValueError:
        v = VehicleType.CAR
    a = Coordinates(lat=from_lat, lon=from_lon)
    b = Coordinates(lat=to_lat, lon=to_lon)
    geom = route_geometry(a, b, v)
    return {"coordinates": geom}  # [[lat,lon], ...]


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "Beeline Business Route Planner",
        "docs": "/docs",
        "health": "/health",
    }
