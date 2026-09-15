"""
Геометрия и время в пути.

Планировщик: быстрый расчёт (гаверсинус × ROAD_FACTOR + скорость ТС).
Карта: по желанию OSRM для отрисовки по дорогам (отдельный эндпоинт).
"""

from __future__ import annotations

import json
import math
import urllib.request
from functools import lru_cache

from .config import AVERAGE_SPEED_KMH, ROAD_DISTANCE_FACTOR
from .models import Coordinates, VehicleType

OSRM_BASE = "https://router.project-osrm.org"


def haversine_km(a: Coordinates, b: Coordinates) -> float:
    r = 6371.0
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def road_distance_km(
    a: Coordinates,
    b: Coordinates,
    vehicle: VehicleType | str = VehicleType.CAR,
) -> float:
    """Быстрая оценка для планировщика (без сетевых вызовов)."""
    return haversine_km(a, b) * ROAD_DISTANCE_FACTOR


def travel_time_minutes(
    a: Coordinates,
    b: Coordinates,
    vehicle: VehicleType | str,
) -> int:
    if isinstance(vehicle, str):
        try:
            vehicle = VehicleType(vehicle)
        except ValueError:
            vehicle = VehicleType.CAR
    speed = AVERAGE_SPEED_KMH.get(vehicle, 25.0)
    dist = road_distance_km(a, b, vehicle)
    if speed <= 0:
        return 9999
    return max(1, int(math.ceil(dist / speed * 60)))


def _profile_for_vehicle(vehicle: VehicleType | str) -> str:
    key = vehicle.value if isinstance(vehicle, VehicleType) else str(vehicle)
    if key == "walking":
        return "foot"
    if key == "bicycle":
        return "bike"
    return "driving"


@lru_cache(maxsize=2048)
def _osrm_geometry(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
    profile: str = "driving",
) -> tuple[tuple[float, float], ...] | None:
    lon1, lat1 = round(lon1, 5), round(lat1, 5)
    lon2, lat2 = round(lon2, 5), round(lat2, 5)
    url = (
        f"{OSRM_BASE}/route/v1/{profile}/"
        f"{lon1},{lat1};{lon2},{lat2}"
        f"?overview=full&geometries=geojson&alternatives=false"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BeelineRoutePlanner/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        coords = tuple(
            (float(c[0]), float(c[1]))
            for c in (data["routes"][0].get("geometry") or {}).get("coordinates") or []
        )
        return coords or None
    except Exception:
        return None


def route_geometry(
    a: Coordinates,
    b: Coordinates,
    vehicle: VehicleType | str = VehicleType.CAR,
) -> list[list[float]]:
    """[[lat, lon], ...] для Leaflet. При сбое OSRM — прямая."""
    profile = _profile_for_vehicle(vehicle)
    res = _osrm_geometry(a.lon, a.lat, b.lon, b.lat, profile)
    if not res:
        return [[a.lat, a.lon], [b.lat, b.lon]]
    return [[lat, lon] for lon, lat in res]
