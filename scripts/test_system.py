import requests
import json
import random

# === НАСТРОЙКИ ===
BASE_URL = "http://localhost:8001/api/v1/optimize"

def print_response(response):
    """Красивый вывод ответа"""
    if response.status_code == 200:
        data = response.json()
        print("✅ SUCCESS (200)")
        print(f"   💨 Wind:      {data['wind_speed']} m/s, {data['wind_deg']}°")
        print(f"   🔋 Energy:    {data['total_energy']} units")
        print(f"   📉 Savings:   {data['savings_percent']}%")
        print(f"   📍 Route:     {' -> '.join(data['route_ids'])}")
        
        # Проверка Геометрии
        geom = data['route_geometry']
        if len(geom) > 0:
            start = geom[0]
            end = geom[-1]
            print(f"   🗺️ Geometry:  {len(geom)} points")
            if start == end:
                print("   🏁 Cycle Check: OK (Start == End)")
            else:
                print("   ❌ Cycle Check: FAIL (Route doesn't loop)")
        print("-" * 40)
    else:
        print(f"❌ ERROR ({response.status_code})")
        print(response.text)

def test_manual_weather():
    print("\n[TEST 1] Manual Weather Override (Hardcoded Wind)")
    print("Scenario: Strong Western Wind (270°)")
    
    payload = {
        "lamps": [
            {"id": "L1", "lat": 55.7560, "lng": 37.6180},
            {"id": "L2", "lat": 55.7600, "lng": 37.6173},
            {"id": "L3", "lat": 55.7558, "lng": 37.6100}, # Запад (против ветра)
            {"id": "L4", "lat": 55.7520, "lng": 37.6173}
        ],
        "depot_lat": 55.7558,
        "depot_lng": 37.6173,
        # Передаем ветер вручную
        "wind_speed": 10.0, 
        "wind_deg": 270
    }
    
    r = requests.post(BASE_URL, json=payload)
    print_response(r)

def test_real_api_weather():
    print("\n[TEST 2] Real API Weather Call (Automatic)")
    print("Scenario: Server fetches real weather for Moscow")
    
    payload = {
        "lamps": [
            {"id": "M1", "lat": 55.750, "lng": 37.620},
            {"id": "M2", "lat": 55.758, "lng": 37.615}
        ],
        "depot_lat": 55.7558,
        "depot_lng": 37.6173
        # Поля wind_speed и wind_deg НЕ передаем
        # Сервер должен сам вызвать weather_service
    }
    
    r = requests.post(BASE_URL, json=payload)
    data = r.json()
    
    print_response(r)
    
    # Дополнительная проверка
    if r.status_code == 200:
        if data['wind_speed'] is not None:
            print("   👀 Verdict: Server returned wind data (Real or Mock).")
        else:
            print("   ⚠️ Verdict: Wind data is null.")

def test_geometry_correctness():
    print("\n[TEST 3] Geometry Structure Validation")
    
    payload = {
        "lamps": [
            {"id": "G1", "lat": 55.756, "lng": 37.618},
            {"id": "G2", "lat": 55.757, "lng": 37.619}
        ],
        "depot_lat": 55.7558,
        "depot_lng": 37.6173
    }
    
    r = requests.post(BASE_URL, json=payload)
    data = r.json()
    
    print_response(r)
    
    # Логические проверки
    ids = data['route_ids']
    geom = data['route_geometry']
    
    # 1. Кол-во точек = Кол-во ламп + 2 (Депо старт + Депо финиш)
    expected_len = len(ids) + 2
    if len(geom) == expected_len:
        print(f"   ✅ Geometry length correct ({len(geom)} points).")
    else:
        print(f"   ❌ Geometry length incorrect! Expected {expected_len}, got {len(geom)}.")

    # 2. Порядок ID должен соответствовать порядку точек в геометрии (кроме депо)
    # Это сложнее проверить без дублирования логики, но визуально мы уже проверили выше.

if __name__ == "__main__":
    print("=== STARTING ML CORE TESTS ===")
    print("Make sure server is running: python main.py")
    
    try:
        # Проверка связи
        requests.get(BASE_URL.replace("/optimize", "/docs"), timeout=1)
        
        test_manual_weather()
        test_real_api_weather()
        test_geometry_correctness()
        
        print("\n=== ALL TESTS COMPLETED ===")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to server.")
        print("Please run 'python main.py' in another terminal first.")