"""
Загрузчик тестовых данных из CSV (Датасет Билайн Бизнес).

Правила из уточнений к ТЗ:
- в планирование не берём статусы «Отменена» и «Выполнена»
- приоритет: Авария > Подключение > Ремонт/Дозаказ
- длительность пока по ориентирам (нормативы позже)
"""

from __future__ import annotations

import csv
from datetime import datetime, time
from pathlib import Path

from .models import (
    Request,
    Engineer,
    Coordinates,
    Skill,
    VehicleType,
    Priority,
)


# ---------------------------------------------------------------------------
# Маппинги
# ---------------------------------------------------------------------------

SKILL_MAP: dict[str, Skill] = {
    # Подключения и дозаказы
    "Заявка на подключение": Skill.CONNECTION_AND_ORDERS,
    "Конвергенция абонента": Skill.CONNECTION_AND_ORDERS,
    "Заказ подключения/Дозаказ оборудования": Skill.CONNECTION_AND_ORDERS,
    "Дозаказ оборудования": Skill.CONNECTION_AND_ORDERS,
    "Переключение на Гбит/с": Skill.CONNECTION_AND_ORDERS,

    # Локальные
    "Роутер. Замена техническим специалистом": Skill.LOCAL_WORKS,
    "TVE/ENT. Замена приставки техником": Skill.LOCAL_WORKS,
    "Информация": Skill.LOCAL_WORKS,
    "Мониторинг": Skill.LOCAL_WORKS,

    # Аварийные
    "Авария": Skill.EMERGENCY_WORKS,
    "Нет линка": Skill.EMERGENCY_WORKS,
    "Разрывы": Skill.EMERGENCY_WORKS,
    "Работа с кабелем": Skill.EMERGENCY_WORKS,
    "TVE/ENT. Другие ошибки": Skill.EMERGENCY_WORKS,
}

# Ориентиры длительности (минуты), пока нет официальной таблицы
DURATION_BY_SKILL: dict[Skill, int] = {
    Skill.EMERGENCY_WORKS: 100,
    Skill.CONNECTION_AND_ORDERS: 90,
    Skill.LOCAL_WORKS: 50,
}

# Статусы, которые НЕ планируем
SKIP_STATUSES = {"отменена", "выполнена"}


def map_skill(hd_type: str) -> Skill:
    key = (hd_type or "").strip()
    return SKILL_MAP.get(key, Skill.LOCAL_WORKS)


def map_priority(hd_type: str) -> Priority:
    """Авария и близкие типы → URGENT, остальное NORMAL."""
    key = (hd_type or "").strip().lower()
    if "авария" in key or "нет линка" in key or "разрывы" in key:
        return Priority.URGENT
    return Priority.NORMAL


def estimate_duration(skill: Skill, window_minutes: int) -> int:
    """
    Берём норматив по типу работ.
    Если окно меньше норматива — не раздуваем duration выше окна.
    """
    base = DURATION_BY_SKILL.get(skill, 60)
    return min(base, max(15, window_minutes))


# ---------------------------------------------------------------------------
# Время
# ---------------------------------------------------------------------------

def parse_time(value: str) -> time:
    value = value.strip()
    dt = datetime.strptime(value, "%d.%m.%Y %H:%M")
    return dt.time()


def window_duration_minutes(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


# ---------------------------------------------------------------------------
# Заявки
# ---------------------------------------------------------------------------

def load_requests(csv_path: str | Path) -> list[Request]:
    path = Path(csv_path)
    requests: list[Request] = []

    with open(path, mode="r", encoding="cp1251", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            try:
                # --- фильтр статусов (есть только в контрольных файлах) ---
                status = (row.get("Статус BK") or row.get("Статус") or "").strip().lower()
                if status in SKIP_STATUSES:
                    continue

                raw_id = str(row.get("Заявка", "")).strip()
                if not raw_id:
                    continue

                window_start = parse_time(row["Начало"])
                window_end = parse_time(row["Окончание"])
                window_minutes = window_duration_minutes(window_start, window_end)
                if window_minutes <= 0:
                    continue

                hd_type = row.get("Тип заявки HD") or row.get("Тип заявки") or ""
                skill = map_skill(hd_type)
                priority = map_priority(hd_type)
                duration = estimate_duration(skill, window_minutes)

                address = (row.get("Адрес") or "").strip() or None

                req = Request(
                    id=raw_id,
                    address=address,
                    coordinates=None,  # геокодер следующим шагом
                    duration_minutes=duration,
                    window_start=window_start,
                    window_end=window_end,
                    priority=priority,
                    required_skill=skill,
                    required_vehicle_type=None,
                )
                requests.append(req)

            except Exception as e:
                print(f"[load_requests] Пропущена строка {row.get('Заявка')}: {e}")
                continue

    return requests


# ---------------------------------------------------------------------------
# Инженеры
# ---------------------------------------------------------------------------

def load_engineers_from_brigades(csv_path: str | Path) -> list[Engineer]:
    path = Path(csv_path)
    brigades: set[str] = set()

    with open(path, mode="r", encoding="cp1251", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            name = (row.get("Бригада") or "").strip()
            if name:
                brigades.add(name)

    engineers: list[Engineer] = []
    for i, name in enumerate(sorted(brigades), start=1):
        engineers.append(
            Engineer(
                id=f"eng_{i:02d}",
                name=name,
                start_coordinates=Coordinates(lat=55.751244, lon=37.618423),
                shift_start=time(9, 0),
                shift_end=time(21, 0),
                skills=[
                    Skill.LOCAL_WORKS,
                    Skill.CONNECTION_AND_ORDERS,
                    Skill.EMERGENCY_WORKS,
                ],
                vehicle_type=VehicleType.CAR,
            )
        )
    return engineers


def create_demo_engineers(count: int = 8) -> list[Engineer]:
    names = [
        "Иванов Алексей",
        "Петров Дмитрий",
        "Сидоров Михаил",
        "Козлов Андрей",
        "Новиков Сергей",
        "Морозов Павел",
        "Волков Артём",
        "Лебедев Игорь",
    ]
    engineers = []
    for i in range(count):
        engineers.append(
            Engineer(
                id=f"eng_{i+1:02d}",
                name=names[i % len(names)],
                start_coordinates=Coordinates(lat=55.751244, lon=37.618423),
                shift_start=time(9, 0),
                shift_end=time(21, 0),
                skills=[
                    Skill.LOCAL_WORKS,
                    Skill.CONNECTION_AND_ORDERS,
                    Skill.EMERGENCY_WORKS,
                ],
                vehicle_type=VehicleType.CAR,
            )
        )
    return engineers


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def load_scenario(csv_path: str | Path) -> tuple[list[Request], list[Engineer]]:
    path = Path(csv_path)
    requests = load_requests(path)
    engineers = load_engineers_from_brigades(path)

    if len(engineers) < 3:
        engineers = create_demo_engineers(count=8)

    return requests, engineers