import requests
import json

# Адрес, где запущен ваш FastAPI
API_URL = "http://127.0.0.1:8000/predict"

def test_predict(data, test_name):
    print(f"\n--- Тест: {test_name} ---")
    print(f"Отправляем данные: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(API_URL, json=data)
        
        if response.status_code == 200:
            result = response.json()
            
            print("\nОТВЕТ МОДЕЛИ:")
            print(f"Вероятность поломки: {result['failure_probability'] * 100:.1f}%")
            print(f"Предсказание (класс): {result['prediction']}")
            print(f"Рекомендация: {result['recommendation']}")
            
            # --- НОВАЯ ЧАСТЬ: Вывод диагноза ---
            print("\nДИАГНОЗ:")
            diagnosis = result['diagnosis']
            print(f"  Причина:    {diagnosis['likely_cause']}")
            print(f"  Описание:   {diagnosis['description']}")
            print(f"  Характер:   {diagnosis['character']}")
            
        else:
            print(f"\nОШИБКА сервера: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("\nОШИБКА: Не удалось подключиться к серверу.")
        print("Убедитесь, что FastAPI запущен (команда: uvicorn main:app --reload)")

# --- ДАННЫЕ ДЛЯ ТЕСТОВ ---

# Сценарий 1: Проблемы с электрикой (скачки напряжения)
test_case_electric = {
    "power_watts": 100,
    "quality_tier": "Budget",
    "age_years": 2.0,
    "operating_hours": 7000,
    "switching_cycles": 700,
    "voltage_spike_count": 8,     # Много скачков!
    "avg_humidity": 50.0,
    "avg_temperature": 20.0,
    "previous_repairs": 0
}

# Сценарий 2: Тепловой перегрев (Мощная лампа + Жарко)
test_case_heat = {
    "power_watts": 250,           # Мощная лампа
    "quality_tier": "Standard",
    "age_years": 3.0,
    "operating_hours": 12000,
    "switching_cycles": 1100,
    "voltage_spike_count": 1,
    "avg_humidity": 60.0,
    "avg_temperature": 35.0,      # Жарко!
    "previous_repairs": 0
}

# Сценарий 3: Старение и влага
test_case_corrosion = {
    "power_watts": 60,
    "quality_tier": "Standard",
    "age_years": 12.0,            # Старая лампа
    "operating_hours": 40000,
    "switching_cycles": 4500,
    "voltage_spike_count": 2,
    "avg_humidity": 90.0,         # Высокая влажность
    "avg_temperature": 10.0,
    "previous_repairs": 1
}

# Сценарий 4: Нормальная лампа
test_case_ok = {
    "power_watts": 50,
    "quality_tier": "Premium",
    "age_years": 1.0,
    "operating_hours": 3000,
    "switching_cycles": 400,
    "voltage_spike_count": 0,
    "avg_humidity": 50.0,
    "avg_temperature": 15.0,
    "previous_repairs": 0
}

# --- ЗАПУСК ТЕСТОВ ---
if __name__ == "__main__":
    print("="*50)
    print("   ЗАПУСК ТЕСТИРОВАНИЯ API (v2.0 с диагностикой)")
    print("="*50)
    
    test_predict(test_case_electric, "Скачки напряжения (Бюджетная)")
    test_predict(test_case_heat, "Перегрев (Мощная лампа)")
    test_predict(test_case_corrosion, "Старение и влага")
    test_predict(test_case_ok, "Нормальная лампа")
    
    print("\n" + "="*50)
    print("   ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*50)