# Билайн Бизнес — Полевой (полный пакет)

Интеллектуальный сервис распределения заявок и построения маршрутов полевых инженеров.

Соответствует ТЗ: ограничения (навык / окно / транспорт), критерии (минимум инженеров → минимум км), карта, перепланирование, объяснения, сравнение с baseline.

## Состав

```
bilayn-route-planner/
├── backend/          # FastAPI + эвристики (greedy / optimized)
├── frontend/         # React + Vite + Leaflet
├── data/             # демо-день 17.08.2026 (24 заявки, 12 бригад, OSM-координаты)
└── README.md
```

## Запуск

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Проверка: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Открыть: http://localhost:5173  
(прокси `/api` → `http://127.0.0.1:8000`)

## Возможности UI

- Карта маршрутов (тёмная подложка CARTO)
- Переключение **Оптимум / Baseline**
- Метрики: инженеры, км, назначено, Δ км
- Сценарии: **Срочная**, **Отмена**, **Недоступен**
- Объяснение назначения по клику на заявку
- Вкладки: маршруты / все заявки / вне плана

## Метрики на демо-дне

| План | Инженеров | Км |
|------|-----------|-----|
| Baseline (greedy) | 6 | 152.4 |
| Optimized | 6 | **134.3** |
| Экономия | — | **~18 км** |

## API (кратко)

| Метод | Путь |
|-------|------|
| GET | `/health` |
| GET | `/scenario/demo` |
| POST | `/plan` |
| POST | `/plan/compare` |
| POST | `/replan` |

## Допущения (ТЗ 3.2)

Основной расчёт: OSRM (по дорогам). Запасной: гаверсинус × 1.3 и таблица скоростей ТС  
(car 30 / public 20 / bicycle 15 / walking 5 км/ч).

## Лимиты ТЗ

до 15 инженеров, до 100 заявок.

## Загрузка CSV

В UI кнопка **CSV** — выбрать файл.

Или через API:

```bash
# только разобрать
curl -F "file=@data/control_distribution.csv" http://127.0.0.1:8000/scenario/csv

# сразу сравнить планы
curl -F "file=@data/synthetic_requests.csv" http://127.0.0.1:8000/plan/csv/compare
```

Два формата в `data/`:
- `control_distribution.csv` — с status_bk и brigade (активные фильтруются)
- `synthetic_requests.csv` — все строки идут в план
