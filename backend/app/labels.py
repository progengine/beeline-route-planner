"""Русские подписи для диспетчера."""

from __future__ import annotations

from .models import Skill, VehicleType

SKILL_RU: dict[str, str] = {
    Skill.LOCAL_WORKS.value: "Локальные работы",
    Skill.CONNECTION_AND_ORDERS.value: "Подключение и дозаказы",
    Skill.EMERGENCY_WORKS.value: "Аварийные работы",
    "local_works": "Локальные работы",
    "connection_and_orders": "Подключение и дозаказы",
    "emergency_works": "Аварийные работы",
}

VEHICLE_RU: dict[str, str] = {
    VehicleType.CAR.value: "автомобиль",
    VehicleType.WALKING.value: "пешком",
    VehicleType.BICYCLE.value: "велосипед",
    VehicleType.PUBLIC_TRANSPORT.value: "общественный транспорт",
    "car": "автомобиль",
    "walking": "пешком",
    "bicycle": "велосипед",
    "public_transport": "общественный транспорт",
}


def skill_ru(skill: str | Skill) -> str:
    key = skill.value if hasattr(skill, "value") else str(skill)
    return SKILL_RU.get(key, key)


def vehicle_ru(vehicle: str | VehicleType) -> str:
    key = vehicle.value if hasattr(vehicle, "value") else str(vehicle)
    return VEHICLE_RU.get(key, key)
