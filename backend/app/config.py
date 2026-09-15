"""
Общие константы и допущения (согласовано с исходным config.py и ТЗ 3.2 / 6).

Допущение по карте: расстояние = гаверсинус × ROAD_DISTANCE_FACTOR,
время = расстояние / средняя скорость типа транспорта.
"""

from __future__ import annotations

from .models import VehicleType

# Средняя скорость передвижения, км/ч
AVERAGE_SPEED_KMH: dict[VehicleType, float] = {
    VehicleType.CAR: 30.0,
    VehicleType.PUBLIC_TRANSPORT: 20.0,
    VehicleType.BICYCLE: 15.0,
    VehicleType.WALKING: 5.0,
}

# прямая → дорожная сеть
ROAD_DISTANCE_FACTOR: float = 1.3

# Лимиты ТЗ (раздел 6)
MAX_ENGINEERS: int = 15
MAX_REQUESTS: int = 100

MINUTES_IN_DAY: int = 24 * 60

# Штраф «открыть нового инженера» в цене вставки (км-эквивалент)
STAFF_WEIGHT_KM: float = 40.0
