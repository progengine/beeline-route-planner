"""
Расчёт расстояния и времени в пути.

Основной способ: OSRM (по дорогам).
Fallback: Haversine + средняя скорость по типу транспорта.
"""

from __future__ import annotations

import math
from typing import Optional

import httpx

from app.models import Coordinates, VehicleType


# ---------------------------------------------------------------------------
# Скорости для fallback (км/ч)
# ---------------------------------------------------------------------------

SPEED_KMH: dict[VehicleType, float] = {
    VehicleType.CAR: 25.0,
    VehicleType.PUBLIC_TRANSPORT: 18.0,
    VehicleType.BICYCLE: 12.0,
    VehicleType.WALKING: 5.0,
}

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
OSRM_TIMEOUT = 3.0  # секунды


# ---------------------------------------------------------------------------
# Haversine (запасной вариант)
# ---------------------------------------------------------------------------

def haversine_km(a: Coordinates, b: Coordinates) -> float:
    R = 6371.0
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(h))


def _fallback_travel(
    a: Coordinates,
    b: Coordinates,
    vehicle: VehicleType,
) -> tuple[float, int]:
    dist = haversine_km(a, b)
    speed = SPEED_KMH.get(vehicle, 20.0)
    minutes = max(1, int(round((dist / speed) * 60)))
    return round(dist, 3), minutes


# ---------------------------------------------------------------------------
# OSRM
# ---------------------------------------------------------------------------

def _osrm_travel(a: Coordinates, b: Coordinates) -> Optional[tuple[float, int]]:
    """
    Запрос к OSRM.
    Возвращает (distance_km, duration_min) или None при ошибке.
    """
    url = OSRM_URL.format(
        lon1=a.lon, lat1=a.lat,
        lon2=b.lon, lat2=b.lat,
    )

    try:
        with httpx.Client(timeout=OSRM_TIMEOUT) as client:
            resp = client.get(url, params={"overview": "false"})
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "Ok":
            return None

        route = data["routes"][0]
        distance_km = route["distance"] / 1000.0
        duration_min = max(1, int(round(route["duration"] / 60.0)))
        return round(distance_km, 3), duration_min

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------

def travel_distance_and_time(
    a: Coordinates,
    b: Coordinates,
    vehicle: VehicleType = VehicleType.CAR,
) -> tuple[float, int]:
    """
    (расстояние_км, время_мин)

    Сначала пробуем OSRM (driving).
    Если не вышло — Haversine + скорость по типу транспорта.
    """
    # OSRM сейчас считаем в режиме driving.
    # Для пешехода/велосипеда позже можно добавить profile=walking/cycling,
    # если поднимете свой OSRM. Публичный demo — в основном driving.
    result = _osrm_travel(a, b)
    if result is not None:
        dist, minutes = result

        # Грубая корректировка под тип транспорта,
        # т.к. публичный OSRM отдаёт автомобильный профиль
        if vehicle == VehicleType.WALKING:
            minutes = max(1, int(minutes * (SPEED_KMH[VehicleType.CAR] / SPEED_KMH[VehicleType.WALKING])))
        elif vehicle == VehicleType.BICYCLE:
            minutes = max(1, int(minutes * (SPEED_KMH[VehicleType.CAR] / SPEED_KMH[VehicleType.BICYCLE])))
        elif vehicle == VehicleType.PUBLIC_TRANSPORT:
            minutes = max(1, int(minutes * (SPEED_KMH[VehicleType.CAR] / SPEED_KMH[VehicleType.PUBLIC_TRANSPORT])))

        return dist, minutes

    return _fallback_travel(a, b, vehicle)


def travel_time_minutes(
    a: Coordinates,
    b: Coordinates,
    vehicle: VehicleType = VehicleType.CAR,
) -> int:
    _, minutes = travel_distance_and_time(a, b, vehicle)
    return minutes