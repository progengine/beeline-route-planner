"""
Доменные модели для сервиса планирования маршрутов "Билайн Бизнес".

Соответствие разделу 2.4 ТЗ:
- Заявка            -> Request
- Инженер           -> Engineer
- Событие переплан.  -> ReplanEvent

Модели результата (раздел 2.4.2):
- RouteStop / EngineerRoute
- UnassignedRequest
- PlanMetrics / PlanResult
"""

from __future__ import annotations


from datetime import time
from enum import Enum
from typing import Optional
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Справочники (раздел 2.4.1 ТЗ)
# ---------------------------------------------------------------------------

class Skill(str, Enum):
    """Требуемый навык / компетенция инженера."""

    LOCAL_WORKS = "local_works"                        # 1. Локальные работы
    CONNECTION_AND_ORDERS = "connection_and_orders"     # 2. Работы на подключение и дозаказы
    EMERGENCY_WORKS = "emergency_works"                 # 3. Аварийные работы


class VehicleType(str, Enum):
    """Тип транспортного средства инженера."""

    CAR = "car"                             # 1. Автомобиль
    WALKING = "walking"                     # 2. Пешеход
    BICYCLE = "bicycle"                     # 3. Велосипед
    PUBLIC_TRANSPORT = "public_transport"   # 4. Общественный транспорт


class Priority(str, Enum):
    """Приоритет заявки."""

    NORMAL = "normal"   # 1. Обычная
    URGENT = "urgent"   # 2. Срочная (выше приоритет при перепланировании)


class EventType(str, Enum):
    """Тип события перепланирования."""

    NEW_URGENT_REQUEST = "new_urgent_request"        # появилась срочная заявка
    CANCEL_REQUEST = "cancel_request"                 # отменена заявка
    ENGINEER_UNAVAILABLE = "engineer_unavailable"     # инженер стал недоступен


class UnassignedReason(str, Enum):
    """
    Причины, по которым заявка не может быть назначена (раздел 2.2 ТЗ).
    Используются для машиночитаемого кода причины; человекочитаемый текст
    для диспетчера кладётся отдельно в UnassignedRequest.explanation.
    """

    NO_AVAILABLE_ENGINEER_AT_TIME = "no_available_engineer_at_time"
    MISSING_REQUIRED_SKILL = "missing_required_skill"
    NO_ENGINEER_WITH_REQUIRED_VEHICLE = "no_engineer_with_required_vehicle"
    DOES_NOT_FIT_TIME_WINDOW_OR_SHIFT = "does_not_fit_time_window_or_shift"


# ---------------------------------------------------------------------------
# Координаты
# ---------------------------------------------------------------------------

class Coordinates(BaseModel):
    lat: float
    lon: float


# ---------------------------------------------------------------------------
# Заявка (раздел 2.4, таблица "Заявка")
# ---------------------------------------------------------------------------

class Request(BaseModel):
    id: str
    address: Optional[str] = None
    coordinates: Optional[Coordinates] = None

    duration_minutes: int = Field(gt=0, description="Длительность работ, мин.")
    window_start: time = Field(description="Начало временного окна")
    window_end: time = Field(description="Конец временного окна")

    priority: Priority = Priority.NORMAL
    required_skill: Skill
    required_vehicle_type: Optional[VehicleType] = Field(
        default=None,
        description="Указывается только если для заявки есть требование к транспорту",
    )

    @field_validator("window_end")
    @classmethod
    def _end_after_start(cls, v: time, info) -> time:
        start = info.data.get("window_start")
        if start is not None and v <= start:
            raise ValueError("window_end должен быть позже window_start")
        return v

    @field_validator("coordinates")
    @classmethod
    def _address_or_coordinates(cls, v, info):
        # ТЗ: "координаты или адрес" — хотя бы один источник локации обязателен.
        # Полная проверка (что задано хотя бы одно из двух) делается на уровне
        # загрузчика данных, т.к. adress приходит позже coordinates при парсинге.
        return v


# ---------------------------------------------------------------------------
# Инженер (раздел 2.4, таблица "Инженер")
# ---------------------------------------------------------------------------

class Engineer(BaseModel):
    id: str
    name: Optional[str] = None

    start_coordinates: Coordinates
    shift_start: time
    shift_end: time

    skills: Annotated[ 
        list[Skill],
        Field(min_length=1, max_length=3)
    ]
    vehicle_type: VehicleType

    @field_validator("skills")
    @classmethod
    def _unique_skills(cls, v: list[Skill]) -> list[Skill]:
        if len(v) != len(set(v)):
            raise ValueError("skills не должны содержать дубликаты")
        return v

    @field_validator("shift_end")
    @classmethod
    def _shift_end_after_start(cls, v: time, info) -> time:
        start = info.data.get("shift_start")
        if start is not None and v <= start:
            raise ValueError("shift_end должен быть позже shift_start")
        return v


# ---------------------------------------------------------------------------
# Событие перепланирования (раздел 2.4, таблица "Событие перепланирования")
# ---------------------------------------------------------------------------

from pydantic import model_validator

class ReplanEvent(BaseModel):
    type: EventType
    event_time: time

    request_id: Optional[str] = None
    engineer_id: Optional[str] = None
    new_request: Optional[Request] = None

    @model_validator(mode="after")
    def check_required_fields(self) -> "ReplanEvent":
        if self.type == EventType.NEW_URGENT_REQUEST and self.new_request is None:
            raise ValueError("new_request обязателен для NEW_URGENT_REQUEST")
        
        if self.type == EventType.CANCEL_REQUEST and self.request_id is None:
            raise ValueError("request_id обязателен для CANCEL_REQUEST")
        
        if self.type == EventType.ENGINEER_UNAVAILABLE and self.engineer_id is None:
            raise ValueError("engineer_id обязателен для ENGINEER_UNAVAILABLE")
        
        return self


# ---------------------------------------------------------------------------
# Результат планирования (раздел 2.4.2 ТЗ)
# ---------------------------------------------------------------------------

class RouteStop(BaseModel):
    """Один визит в маршруте инженера."""

    request_id: str
    planned_arrival: time
    planned_start: time
    planned_end: time 
    travel_distance_km: float
    travel_time_minutes: int
    
    
    
    
    @field_validator("planned_end")
    @classmethod
    def _end_after_start(cls, v: time, info) -> time:
        start = info.data.get("planned_start")
        if start is not None and v <= start:
            raise ValueError("planned_end должен быть позже planned_start")
        return v


class EngineerRoute(BaseModel):
    """Упорядоченный маршрут одного инженера."""

    engineer_id: str
    stops: list[RouteStop] = Field(default_factory=list)
    total_distance_km: float = 0.0


class UnassignedRequest(BaseModel):
    """Заявка, которую не удалось назначить, с явной причиной."""

    request_id: str
    reason: UnassignedReason
    explanation: str  # человекочитаемый текст для диспетчера


class PlanMetrics(BaseModel):
    """Обязательные метрики сравнения планов (раздел 2.3 ТЗ)."""

    engineers_used: int
    distance_by_engineer_km: dict[str, float]
    total_distance_km: float


class PlanResult(BaseModel):
    """Итоговый план: маршруты, неназначенные заявки, метрики, объяснения."""

    routes: list[EngineerRoute]
    unassigned: list[UnassignedRequest]
    metrics: PlanMetrics
    explanations: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "request_id -> объяснение назначения: почему заявка досталась "
            "этому инженеру, какие ограничения учтены, почему такой маршрут"
        ),
    )
    changed_request_ids: list[str] = Field(
        default_factory=list,
        description="Заполняется при перепланировании: что изменилось относительно предыдущего плана",
    )
