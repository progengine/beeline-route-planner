"""
Импорт CSV Билайн (оба формата из ТЗ):
1) Контрольное распределение — есть status_bk, brigade
2) Синтетика — только заявки

Поддержка:
- разделитель , или ;
- заголовки EN (request_id, ...) и RU (Заявка, ...)
- фильтр активных статусов для control
- координаты из кэша улиц / центра района
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime, time
from typing import Any

from .models import (
    Coordinates,
    Engineer,
    Priority,
    Request,
    Skill,
    VehicleType,
)

ACTIVE_STATUSES = {
    "Не отправлена",
    "Отправлена",
    "В пути",
    "В работе",
    "Просрочена",
}

SKILL_MAP: dict[str, Skill] = {
    "Заявка на подключение": Skill.CONNECTION_AND_ORDERS,
    "Конвергенция абонента": Skill.CONNECTION_AND_ORDERS,
    "Заказ подключения/Дозаказ оборудования": Skill.CONNECTION_AND_ORDERS,
    "Дозаказ оборудования": Skill.CONNECTION_AND_ORDERS,
    "Переключение на Гбит/с": Skill.CONNECTION_AND_ORDERS,
    "Роутер. Замена техническим специалистом": Skill.LOCAL_WORKS,
    "TVE/ENT. Замена приставки техником": Skill.LOCAL_WORKS,
    "Информация": Skill.LOCAL_WORKS,
    "Мониторинг": Skill.LOCAL_WORKS,
    "Авария": Skill.EMERGENCY_WORKS,
    "Нет линка": Skill.EMERGENCY_WORKS,
    "Разрывы": Skill.EMERGENCY_WORKS,
    "Работа с кабелем": Skill.EMERGENCY_WORKS,
    "TVE/ENT. Другие ошибки": Skill.EMERGENCY_WORKS,
}

# Nominatim-кэш по фрагменту адреса (Москва)
STREET_COORDS: list[tuple[str, float, float]] = [
    ("волгоградский", 55.702338, 37.782875),
    ("маяковского", 55.739774, 37.659908),
    ("грайвороновская", 55.719042, 37.730050),
    ("михайлова", 55.727030, 37.765960),
    ("институтская", 55.721992, 37.782190),
    ("новокузьминская", 55.714359, 37.789796),
    ("окская", 55.714471, 37.769522),
    ("юных ленинцев", 55.698118, 37.778604),
    ("дубровская", 55.726739, 37.669561),
    ("артюхиной", 55.698497, 37.737800),
    ("карачаровская", 55.733218, 37.745014),
    ("рязанский", 55.718455, 37.790255),
    ("ферганская", 55.701078, 37.825010),
    ("самаркандский", 55.697579, 37.816217),
    ("орехово-зуевский", 55.731152, 37.753472),
    ("рогожский", 55.742513, 37.668471),
    ("машкова", 55.762415, 37.648995),
    ("текстильщиков", 55.706885, 37.743199),
    ("паперника", 55.721323, 37.793512),
    ("калитниковская", 55.736168, 37.686206),
    ("чуйкова", 55.697144, 37.762011),
    ("талалихина", 55.740000, 37.670000),
    ("международная", 55.745000, 37.680000),
    ("новорогожская", 55.741000, 37.672000),
    ("чистова", 55.708000, 37.735000),
    ("трофимова", 55.718000, 37.675000),
    ("малышева", 55.705000, 37.730000),
    ("бронницкая", 55.732000, 37.715000),
    ("авиамоторная", 55.755000, 37.715000),
    ("полетаева", 55.700000, 37.770000),
    ("зарайская", 55.720000, 37.785000),
    ("саратовская", 55.705000, 37.740000),
    ("нижегородская", 55.738000, 37.700000),
    ("смирновская", 55.735000, 37.725000),
    ("зеленодольская", 55.710000, 37.760000),
    ("боровая", 55.758000, 37.695000),
    ("стройковская", 55.742000, 37.665000),
    ("синичкина", 55.755000, 37.705000),
    ("волжский", 55.707000, 37.745000),
    ("земляной вал", 55.760000, 37.655000),
    ("чистопольская", 55.730000, 37.740000),
    ("красноказарменная", 55.758000, 37.710000),
    ("сторожевая", 55.752000, 37.700000),
    ("ташкентская", 55.710000, 37.820000),
    ("семеновская", 55.780000, 37.720000),
    ("ферганский", 55.705000, 37.830000),
]

DISTRICT_COORDS: dict[str, tuple[float, float]] = {
    "Кузьминки": (55.705, 37.765),
    "Таганский": (55.740, 37.655),
    "Текстильщики": (55.709, 37.733),
    "Рязанский": (55.715, 37.790),
    "Южнопортовый": (55.720, 37.680),
    "Нижегородский": (55.735, 37.720),
    "Лефортово": (55.760, 37.700),
    "Выхино": (55.715, 37.820),
    "Басманный": (55.765, 37.670),
}


def _norm(s: str | None) -> str:
    return (s or "").strip()


def _get(row: dict[str, str], *keys: str) -> str:
    for k in keys:
        if k in row and row[k] is not None and str(row[k]).strip() != "":
            return str(row[k]).strip()
    # case-insensitive
    lower = {k.lower(): v for k, v in row.items()}
    for k in keys:
        if k.lower() in lower and lower[k.lower()]:
            return str(lower[k.lower()]).strip()
    return ""


def parse_time(value: str) -> time:
    value = value.strip()
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%H:%M", "%H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.time()
        except ValueError:
            continue
    raise ValueError(f"Не удалось разобрать время: {value!r}")


def map_skill(hd: str, bk: str = "") -> Skill:
    if hd in SKILL_MAP:
        return SKILL_MAP[hd]
    if bk in ("Подключение", "Дозаказ"):
        return Skill.CONNECTION_AND_ORDERS
    if bk == "Локальная заявка":
        return Skill.LOCAL_WORKS
    if bk == "Глобальная проблема":
        return Skill.EMERGENCY_WORKS if "Авария" in hd else Skill.LOCAL_WORKS
    return Skill.LOCAL_WORKS


def estimate_duration(hd: str, bk: str, window_min: int, gigabit: str) -> int:
    if "Авария" in hd:
        base = 80
    elif bk == "Подключение" or "Конвергенция" in hd or "подключен" in hd.lower():
        base = 90 if gigabit == "Да" else 70
    elif bk == "Дозаказ" or "Дозаказ" in hd:
        base = 50
    elif "Переключение" in hd:
        base = 55
    elif "Мониторинг" in hd:
        base = 40
    else:
        base = 45
    return max(20, min(base, max(20, window_min - 10)))


def coords_for(address: str, district: str, rid: str) -> Coordinates:
    low = address.lower()
    for key, lat, lon in STREET_COORDS:
        if key in low:
            # лёгкий jitter чтобы маркеры не слипались
            h = int(hashlib.md5(rid.encode()).hexdigest()[:4], 16)
            lat += ((h % 17) - 8) * 0.00025
            lon += ((h // 17) % 17 - 8) * 0.00025
            return Coordinates(lat=round(lat, 6), lon=round(lon, 6))
    lat, lon = DISTRICT_COORDS.get(district, (55.75, 37.62))
    h = int(hashlib.md5(rid.encode()).hexdigest()[:4], 16)
    lat += ((h % 17) - 8) * 0.0008
    lon += ((h // 17) % 17 - 8) * 0.0008
    return Coordinates(lat=round(lat, 6), lon=round(lon, 6))


def _detect_delimiter(sample: str) -> str:
    first = sample.splitlines()[0] if sample else ""
    return ";" if first.count(";") > first.count(",") else ","


def parse_csv_text(text: str, only_active: bool = True) -> tuple[list[Request], list[Engineer], dict[str, Any]]:
    """Парсит CSV-текст → requests, engineers, meta."""
    # strip BOM
    if text.startswith("\ufeff"):
        text = text[1:]
    delim = _detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if not reader.fieldnames:
        raise ValueError("Пустой CSV или нет заголовка")

    rows = list(reader)
    requests: list[Request] = []
    brigades: set[str] = set()
    skipped = {"completed": 0, "cancelled": 0, "bad": 0}

    for row in rows:
        try:
            rid = _get(row, "request_id", "Заявка", "id")
            if not rid:
                skipped["bad"] += 1
                continue

            status = _get(row, "status_bk", "Статус BK", "status")
            if only_active and status:
                if status in ("Выполнена",):
                    skipped["completed"] += 1
                    continue
                if status in ("Отменена",):
                    skipped["cancelled"] += 1
                    continue
                if status not in ACTIVE_STATUSES:
                    # неизвестный статус — пропускаем только явно закрытые
                    pass

            start_s = _get(row, "start", "Начало")
            end_s = _get(row, "end", "Окончание")
            if not start_s or not end_s:
                skipped["bad"] += 1
                continue

            window_start = parse_time(start_s)
            window_end = parse_time(end_s)
            wmin = (window_end.hour * 60 + window_end.minute) - (
                window_start.hour * 60 + window_start.minute
            )
            if wmin <= 0:
                skipped["bad"] += 1
                continue

            hd = _get(row, "request_type_hd", "Тип заявки HD")
            bk = _get(row, "request_type_bk", "Тип заявки BK")
            address = _get(row, "address", "Адрес")
            district = _get(row, "district", "Район")
            brigade = _get(row, "brigade", "Бригада")
            conn = _get(row, "connection", "Подключение")
            gigabit = _get(row, "gigabit_connection", "Гигабитное подключение")

            if brigade:
                brigades.add(brigade)

            vehicle = None
            if conn in ("FMC", "FTTB") or gigabit == "Да" or bk in ("Подключение", "Дозаказ"):
                vehicle = VehicleType.CAR

            priority = Priority.URGENT if status == "Просрочена" or "Авария" in hd else Priority.NORMAL
            duration = estimate_duration(hd, bk, wmin, gigabit)

            requests.append(
                Request(
                    id=rid,
                    address=address or None,
                    coordinates=coords_for(address, district, rid),
                    duration_minutes=duration,
                    window_start=window_start,
                    window_end=window_end,
                    priority=priority,
                    required_skill=map_skill(hd, bk),
                    required_vehicle_type=vehicle,
                )
            )
        except Exception:
            skipped["bad"] += 1
            continue

    engineers = _engineers_from_brigades(brigades) if brigades else create_demo_engineers(12)

    meta = {
        "source": "csv_upload",
        "rows_total": len(rows),
        "active_requests": len(requests),
        "engineers": len(engineers),
        "skipped": skipped,
        "delimiter": delim,
    }
    return requests, engineers, meta


def _engineers_from_brigades(brigades: set[str]) -> list[Engineer]:
    engineers: list[Engineer] = []
    for i, name in enumerate(sorted(brigades), start=1):
        # база — районный центр по имени, иначе Москва
        lat, lon = 55.751244, 37.618423
        for dist, (dlat, dlon) in DISTRICT_COORDS.items():
            if dist.lower() in name.lower():
                lat, lon = dlat, dlon
                break
        # разнесём базы
        lat += (i % 5) * 0.004
        lon += (i % 4) * 0.005
        engineers.append(
            Engineer(
                id=f"eng_{i:02d}",
                name=name,
                start_coordinates=Coordinates(lat=round(lat, 6), lon=round(lon, 6)),
                shift_start=time(10, 0),
                shift_end=time(22, 0),
                skills=[
                    Skill.LOCAL_WORKS,
                    Skill.CONNECTION_AND_ORDERS,
                    Skill.EMERGENCY_WORKS,
                ],
                vehicle_type=VehicleType.CAR,
            )
        )
    return engineers


def create_demo_engineers(count: int = 12) -> list[Engineer]:
    names = [
        "Бригада Соколов",
        "Бригада Мельников",
        "Бригада Матвеев",
        "Бригада Попов",
        "Бригада Арташкин",
        "Бригада Комарь",
        "Бригада Каушнян",
        "Бригада Зверев",
        "Бригада Перов",
        "Бригада Белузин",
        "Бригада Гусаковский",
        "Бригада Свеженцев",
    ]
    districts = list(DISTRICT_COORDS.items())
    engineers: list[Engineer] = []
    for i in range(count):
        dist_name, (lat, lon) = districts[i % len(districts)]
        engineers.append(
            Engineer(
                id=f"eng_{i+1:02d}",
                name=names[i % len(names)],
                start_coordinates=Coordinates(lat=lat, lon=lon),
                shift_start=time(10, 0),
                shift_end=time(22, 0),
                skills=[
                    Skill.LOCAL_WORKS,
                    Skill.CONNECTION_AND_ORDERS,
                    Skill.EMERGENCY_WORKS,
                ],
                vehicle_type=VehicleType.CAR,
            )
        )
    return engineers
