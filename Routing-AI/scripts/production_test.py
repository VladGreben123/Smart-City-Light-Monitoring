import requests
import json
import time

# ==========================================
# КОНФИГУРАЦИЯ PROD
# ==========================================
API_URL = "http://localhost:8002/api/v1/optimize"
HEADERS = {'Content-Type': 'application/json'}

# Реальные координаты
DEPOT_COORDS = {"lat": 55.7528, "lng": 48.7452}

# Список "перегоревших" ламп от системы мониторинга
LAMPS_INPUT = [
    {"id": "lamp_1", "lat": 55.751052, "lng": 48.750037},
    {"id": "lamp_2", "lat": 55.749079, "lng":  48.741976},
    {"id": "lamp_3", "lat": 55.751942, "lng": 48.745915},
    # Добавляем больше точек для демонстрации работы алгоритма (N > 3)
    {"id": "lamp_4", "lat": 55.753500, "lng": 48.748000},
    {"id": "lamp_5", "lat": 55.748500, "lng": 48.751000},
    {"id": "lamp_6", "lat": 55.750500, "lng": 48.743500},
]

def send_request(payload, test_name):
    print(f"\n{'='*20} TEST: {test_name} {'='*20}")
    
    # 1. Вывод того, что мы отправляем (Payload)
    print("\n[REQUEST] Отправляем данные (Production Format):")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    start_time = time.time()
    try:
        response = requests.post(API_URL, json=payload, headers=HEADERS)
        latency = (time.time() - start_time) * 1000

        # 2. Вывод того, что получили (Response)
        if response.status_code == 200:
            data = response.json()
            print(f"\n[RESPONSE] Успех (200 OK) | Latency: {latency:.0f}ms")
            
            # Визуализация данных так, как их увидит Frontend
            print("\n--- Данные для Карты (Frontend) ---")
            print(f"Wind Speed: {data['wind_speed']} m/s")
            print(f"Wind Deg:   {data['wind_deg']} deg")
            
            print("\n--- Геометрия маршрута (для Leaflet/Google Maps) ---")
            # Вывод первых 3 точек и последних 2 для краткости
            coords = data['route_geometry']
            if len(coords) > 5:
                print(f"Points: [ {coords[0]}, {coords[1]}, {coords[2]}, ... {coords[-2]}, {coords[-1]} ]")
            else:
                print(f"Points: {coords}")
            
            print(f"\n--- Маршрут дрона (Drone Pilot View) ---")
            route_str = " -> ".join(data['route_ids'])
            print(f"Sequence: Depot -> {route_str} -> Depot")
            
            print(f"\n--- ML Статистика (Analytics Dashboard) ---")
            print(f"Naive Energy Cost: {data['naive_energy']}")
            print(f"Smart AI Cost:     {data['total_energy']}")
            print(f"Saved Battery:     {data['savings_percent']}%")
            
        else:
            print(f"\n[ERROR] Server returned {response.status_code}")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print("\n[FATAL] Ошибка подключения. Сервер не запущен?")

def main():
    print("STARTING PRODUCTION SIMULATION...")

    # ==========================================
    # СЦЕНАРИЙ 1: Рабочий режим (Backend -> ML Core)
    # ==========================================
    # Система не знает погоду, ML-ядро должно само её узнать
    payload_auto = {
        "lamps": LAMPS_INPUT,
        "depot_lat": DEPOT_COORDS["lat"],
        "depot_lng": DEPOT_COORDS["lng"]
        # Поля wind_speed и wind_deg отсутствуют -> ядро вызывает OpenWeatherMap
    }
    send_request(payload_auto, "Auto Weather (Real Data)")

    # ==========================================
    # СЦЕНАРИЙ 2: Демо-режим / Тестирование (Frontend -> ML Core)
    # ==========================================
    # Мы хотим показать, как алгоритм справляется с ураганным ветром
    payload_manual = {
        "lamps": LAMPS_INPUT,
        "depot_lat": DEPOT_COORDS["lat"],
        "depot_lng": DEPOT_COORDS["lng"],
        "wind_speed": 15.0, # Искусственно задаем шторм
        "wind_deg": 90.0    # Восточный ветер
    }
    send_request(payload_manual, "Manual Weather (Demo/Debug Mode)")

if __name__ == "__main__":
    main()