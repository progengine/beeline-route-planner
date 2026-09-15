"""Работа со временем смены / окон."""

from __future__ import annotations

from datetime import time, timedelta, datetime


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def minutes_to_time(m: int) -> time:
    m = max(0, min(m, 23 * 60 + 59))
    return time(m // 60, m % 60)


def add_minutes(t: time, minutes: int) -> time:
    return minutes_to_time(time_to_minutes(t) + minutes)
