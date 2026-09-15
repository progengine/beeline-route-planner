from pathlib import Path
from app.data_loader import load_scenario

# Путь к CSV (поправь имя файла, если оно чуть другое)
CSV_PATH = Path(__file__).parent.parent / "data" / "Восток Контрольное распределение. (1).csv"

print("Читаем файл:", CSV_PATH)
print("Файл существует:", CSV_PATH.exists())

requests, engineers = load_scenario(CSV_PATH)

print(f"\nЗаявок загружено: {len(requests)}")
print(f"Инженеров загружено: {len(engineers)}")

print("\n--- Первая заявка ---")
if requests:
    r = requests[0]
    print(f"ID: {r.id}")
    print(f"Адрес: {r.address}")
    print(f"Окно: {r.window_start} – {r.window_end}")
    print(f"Длительность: {r.duration_minutes} мин")
    print(f"Навык: {r.required_skill}")

print("\n--- Первый инженер ---")
if engineers:
    e = engineers[0]
    print(f"ID: {e.id}")
    print(f"Имя: {e.name}")
    print(f"Смена: {e.shift_start} – {e.shift_end}")
    print(f"Навыки: {e.skills}")
    print(f"Транспорт: {e.vehicle_type}")