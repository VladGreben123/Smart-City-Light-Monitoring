import asyncio
import sys

# Импортируем функцию напрямую из файла сервиса
from weather_service import get_wind_data

async def test_weather_module():
    print("--- TESTING WEATHER SERVICE MODULE ---")
    
    # Тестовые координаты (Москва, Красная площадь)
    TEST_LAT = 55.7558
    TEST_LON = 37.6173

    print(f"\n[Input] Coordinates: Lat {TEST_LAT}, Lon {TEST_LON}")
    print("[Action] Calling get_wind_data()...")
    
    # Вызываем функцию получения погоды
    speed, deg = await get_wind_data(TEST_LAT, TEST_LON)
    
    print("\n[Result]")
    print(f"Wind Speed: {speed} m/s")
    print(f"Wind Deg:   {deg}°")
    
    # Интерпретация результата
    if speed == 0.0 and deg == 0.0:
        print("\n⚠️ WARNING: Received zero values. Check your API Key or internet connection.")
    elif speed > 50:
        print("\n⚠️ WARNING: Unrealistic wind speed. Check units.")
    else:
        print("\n✅ SUCCESS: Data received.")

    # Визуализация направления (для проверки)
    directions = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    idx = int((deg + 22.5) // 45) % 8
    print(f"Direction: Wind is blowing FROM the {directions[idx]}")

if __name__ == "__main__":
    # Запуск асинхронной функции
    try:
        asyncio.run(test_weather_module())
    except Exception as e:
        print(f"\n[ERROR] Critical failure: {e}")