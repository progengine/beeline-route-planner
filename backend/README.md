# Билайн Бизнес — сервис планирования маршрутов (Backend)

Рабочий прототип по ТЗ: распределение заявок, VRPTW-эвристика, перепланирование, объяснения, сравнение с baseline.

## Быстрый старт

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger: http://localhost:8000/docs  
- Health: http://localhost:8000/health  
- Демо-день: http://localhost:8000/scenario/demo  

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | статус |
| GET | `/scenario/demo` | 12 бригад, 24 активные заявки, координаты OSM |
| POST | `/plan` | `{"engineers","requests","mode":"greedy\|optimized"}` |
| POST | `/plan/compare` | baseline + optimized + дельта метрик |
| POST | `/replan` | событие: срочная / отмена / инженер недоступен |

## Алгоритмы (ТЗ 2.2–2.3)

**Ограничения (жёсткие):**
- навык инженера ⊇ required_skill  
- тип транспорта (если задан у заявки)  
- временное окно + смена + время в пути  

**Критерии оптимальности:**
1. минимум инженеров  
2. при равном штате — минимум суммарного пробега  

**Baseline (`greedy`):** first-fit в порядке срочность → окно.  

**Optimized:** best insertion (штраф за нового инженера) → pack штата → 2-opt.  

**Допущение по карте (ТЗ 3.2):**  
`distance = haversine × 1.3`, `time = distance / speed(vehicle)`.

## Результат на демо-дне 17.08.2026

| План | Инженеров | Км | Неназначенных |
|------|-----------|-----|----------------|
| Greedy | 6 | 152.4 | 0 |
| Optimized | 6 | **134.3** | 0 |
| Δ | 0 | **−18.1 км** | — |

Данные: активные статусы из CSV Билайн, координаты Nominatim/OSM.

## Структура

```
backend/
  app/
    models.py       # Request, Engineer, ReplanEvent, PlanResult (ТЗ 2.4)
    data_loader.py  # CSV (cp1251, ;) → модели
    config.py       # скорости, лимиты 15/100
    geo.py          # гаверсинус × 1.3
    simulate.py     # симуляция маршрута
    greedy.py       # baseline
    optimized.py    # insertion + pack + 2-opt
    replan.py       # 3 типа событий
    explain.py      # тексты для диспетчера
    schemas.py      # DTO
    main.py         # FastAPI
  data/
    beeline-day-2026-08-17.json
  requirements.txt
```

## Статус относительно исходного чеклиста

- [x] Модель данных  
- [x] Загрузчик CSV/JSON  
- [x] Базовый (жадный) алгоритм  
- [x] Эвристика лучше baseline (вместо OR-Tools — pip ortools в среде недоступен)  
- [x] Модуль объяснений  
- [x] Перепланирование по событию  
- [x] Сравнение метрик  
- [x] Тестовый набор (реальный день + геокод)  
- [ ] UI/карта — во фронтенде (отдельный пакет)

## Лимиты ТЗ

`MAX_ENGINEERS = 15`, `MAX_REQUESTS = 100` — в `config.py`.
