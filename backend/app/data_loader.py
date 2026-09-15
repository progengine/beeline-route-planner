"""
Загрузчик тестовых данных из CSV (Датасет Билайн Бизнес).

Поддерживает:
- Контрольное распределение
- Синтетические данные

Кодировка файлов: cp1251
Разделитель: ;
"""

from __future__ import annotations

import csv
from datetime import datetime, time
from pathlib import Path
from typing import Optional

from .models import (
    Request,
    Engineer,
    Coordinates,
    Skill,
    VehicleType,
    Priority,
)


# ---------------------------------------------------------------------------
# Маппинг «Тип заявки HD» → наш Skill
# ---------------------------------------------------------------------------

SKILL_MAP: dict[str, Skill] = {
    # Работы на подключение и дозаказы
    "Заявка на подключение": Skill.CONNECTION_AND_ORDERS,
    "Конвергенция абонента": Skill.CONNECTION_AND_ORDERS,
    "Заказ подключения/Дозаказ оборудования": Skill.CONNECTION_AND_ORDERS,
    "Дозаказ оборудования": Skill.CONNECTION_AND_ORDERS,
    "Переключение на Гбит/с": Skill.CONNECTION_AND_ORDERS,

    # Локальные работы
    "Роутер. Замена техническим специалистом": Skill.LOCAL_WORKS,
    "TVE/ENT. Замена приставки техником": Skill.LOCAL_WORKS,
    "Информация": Skill.LOCAL_WORKS,
    "Мониторинг": Skill.LOCAL_WORKS,

    # Аварийные работы
    "Авария": Skill.EMERGENCY_WORKS,
    "Нет линка": Skill.EMERGENCY_WORKS,
    "Разрывы": Skill.EMERGENCY_WORKS,
    "Работа с кабелем": Skill.EMERGENCY_WORKS,
    "TVE/ENT. Другие ошибки": Skill.EMERGENCY_WORKS,
}


def map_skill(hd_type: str) -> Skill:
    """Преобразует значение из колонки 'Тип заявки HD' в Enum Skill."""
    key = (hd_type or "").strip()
    return SKILL_MAP.get(key, Skill.LOCAL_WORKS)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def parse_time(value: str) -> time:
    """
    '17.08.2026 20:00' → time(20, 0)
    """
    value = value.strip()
    dt = datetime.strptime(value, "%d.%m.%Y %H:%M")
    return dt.time()


def calc_duration_minutes(start: time, end: time) -> int:
    """Длительность окна в минутах."""
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    return end_min - start_min


# ---------------------------------------------------------------------------
# Загрузка заявок
# ---------------------------------------------------------------------------

ACTIVE_STATUSES = {
    "Не отправлена",
    "Отправлена",
    "В пути",
    "В работе",
    "Просрочена",
}


def estimate_work_minutes(hd_type: str, window_minutes: int) -> int:
    """Длительность работ ≠ длина окна. Оценка по типу HD, не больше окна-10."""
    hd = (hd_type or "").strip()
    if "Авария" in hd:
        base = 80
    elif "подключен" in hd.lower() or "Конвергенция" in hd:
        base = 70
    elif "Дозаказ" in hd:
        base = 50
    elif "Переключение" in hd:
        base = 55
    else:
        base = 45
    return max(20, min(base, max(20, window_minutes - 10)))


def load_requests(csv_path: str | Path, only_active: bool = True) -> list[Request]:
    """
    Читает CSV и возвращает список Request.

    Ожидаемые колонки:
    - Заявка, Тип заявки HD, Начало, Окончание, Адрес
    - опционально: Статус BK, Подключение, Гигабитное подключение
    """
    path = Path(csv_path)
    requests: list[Request] = []

    with open(path, mode="r", encoding="cp1251", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            try:
                raw_id = str(row.get("Заявка", "")).strip()
                if not raw_id:
                    continue

                status = (row.get("Статус BK") or "").strip()
                if only_active and status and status not in ACTIVE_STATUSES:
                    continue

                window_start = parse_time(row["Начало"])
                window_end = parse_time(row["Окончание"])
                window_min = calc_duration_minutes(window_start, window_end)
                if window_min <= 0:
                    continue

                hd = row.get("Тип заявки HD", "")
                duration = estimate_work_minutes(hd, window_min)
                address = (row.get("Адрес") or "").strip() or None

                conn = (row.get("Подключение") or "").strip()
                gigabit = (row.get("Гигабитное подключение") or "").strip()
                vehicle = None
                if conn in ("FMC", "FTTB") or gigabit == "Да":
                    vehicle = VehicleType.CAR

                priority = Priority.URGENT if status == "Просрочена" else Priority.NORMAL

                req = Request(
                    id=raw_id,
                    address=address,
                    coordinates=None,
                    duration_minutes=duration,
                    window_start=window_start,
                    window_end=window_end,
                    priority=priority,
                    required_skill=map_skill(hd),
                    required_vehicle_type=vehicle,
                )
                requests.append(req)

            except Exception as e:
                print(f"[load_requests] Пропущена строка {row.get('Заявка')}: {e}")
                continue

    return requests


# ---------------------------------------------------------------------------
# Генерация инженеров
# ---------------------------------------------------------------------------

def load_engineers_from_brigades(csv_path: str | Path) -> list[Engineer]:
    """
    В CSV нет полноценных инженеров.
    Берём уникальные значения из колонки «Бригада» и создаём инженеров.

    Пока ставим:
    - все навыки
    - автомобиль
    - смену 09:00–21:00
    - стартовую точку — центр Москвы (заглушка)
    """
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
        eng = Engineer(
            id=f"eng_{i:02d}",
            name=name,
            start_coordinates=Coordinates(lat=55.751244, lon=37.618423),  # Москва
            shift_start=time(9, 0),
            shift_end=time(21, 0),
            skills=[
                Skill.LOCAL_WORKS,
                Skill.CONNECTION_AND_ORDERS,
                Skill.EMERGENCY_WORKS,
            ],
            vehicle_type=VehicleType.CAR,
        )
        engineers.append(eng)

    return engineers


def create_demo_engineers(count: int = 8) -> list[Engineer]:
    """
    Полностью синтетические инженеры (когда в CSV нет колонки «Бригада»
    или она почти пустая — как в синтетических файлах).
    """
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
        eng = Engineer(
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
        engineers.append(eng)

    return engineers


# ---------------------------------------------------------------------------
# Главная точка входа
# ---------------------------------------------------------------------------

def load_scenario(csv_path: str | Path) -> tuple[list[Request], list[Engineer]]:
    """
    Загружает полный сценарий:
    - заявки из CSV
    - инженеров (из бригад или демо-набор)
    """
    path = Path(csv_path)

    requests = load_requests(path)
    engineers = load_engineers_from_brigades(path)

    # Если бригад почти нет (синтетика) — берём демо-инженеров
    if len(engineers) < 3:
        engineers = create_demo_engineers(count=8)

    return requests, engineers