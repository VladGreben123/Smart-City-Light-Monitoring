from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional
import pandas as pd
import joblib
import os

# --- 1. КОНФИГУРАЦИЯ И ЗАГРУЗКА МОДЕЛИ ---

app = FastAPI(
    title="LED Lamp Failure Prediction API",
    description="API для предсказания вероятности выхода из строя уличных LED-ламп с диагностикой.",
    version="2.0.0"
)

MODEL_PATH = 'models/lamp_failure_model.pkl'

if not os.path.exists(MODEL_PATH):
    raise RuntimeError(f"Файл модели {MODEL_PATH} не найден.")

model = joblib.load(MODEL_PATH)
QUALITY_MAP = {'Budget': 0, 'Standard': 1, 'Premium': 2}

# --- 2. СХЕМЫ ДАННЫХ ---

class LampData(BaseModel):
    power_watts: int = Field(..., example=100, description="Мощность лампы в Ваттах")
    quality_tier: Literal['Budget', 'Standard', 'Premium'] = Field(..., example="Standard", description="Класс качества")
    age_years: float = Field(..., example=5.5, description="Возраст установки в годах")
    operating_hours: int = Field(..., example=20000, description="Общая наработка в часах")
    switching_cycles: int = Field(..., example=2000, description="Количество циклов вкл/выкл")
    voltage_spike_count: int = Field(..., example=2, description="Кол-во скачков напряжения")
    avg_humidity: float = Field(..., example=65.0, description="Средняя влажность %")
    avg_temperature: float = Field(..., example=15.0, description="Средняя температура C")
    previous_repairs: int = Field(..., example=0, description="Количество прошлых ремонтов")

class DiagnosisResult(BaseModel):
    likely_cause: str = Field(..., description="Вероятная причина неисправности")
    description: str = Field(..., description="Подробное описание проблемы")
    character: str = Field(..., description="Характер отказа (внезапный/постепенный)")

class PredictionResponse(BaseModel):
    failure_probability: float
    prediction: int
    recommendation: str
    diagnosis: DiagnosisResult

# --- 3. ЛОГИКА ДИАГНОСТИКИ ---

def get_failure_diagnosis(data: LampData, probability: float) -> DiagnosisResult:
    """
    Экспертная система, определяющая причину поломки на основе входных данных.
    Проверяет факторы в порядке критичности.
    """
    
    # Если риска нет, возвращаем "все нормально"
    if probability < 0.3:
        return DiagnosisResult(
            likely_cause="Нормальная эксплуатация",
            description="Устройство работает в штатном режиме, критических отклонений не выявлено.",
            character="Нет"
        )

    # 1. Проверка скачков напряжения (Электрический стресс)
    # Для дешевых ламп даже 3-4 скачка критичны
    spike_threshold = 3 if data.quality_tier == 'Budget' else 6
    if data.voltage_spike_count >= spike_threshold:
        return DiagnosisResult(
            likely_cause="Электрический пробой драйвера",
            description=f"Зафиксировано {data.voltage_spike_count} скачков напряжения. Вердикт: выход из строя конденсаторов или предохранителя блока питания.",
            character="Внезапный отказ"
        )

    # 2. Проверка перегрева (Тепловой стресс)
    # Если мощность > 150 Вт и температура > 25 градусов
    if data.power_watts >= 150 and data.avg_temperature > 25:
        return DiagnosisResult(
            likely_cause="Тепловая деградация компонентов",
            description=f"Мощная лампа ({data.power_watts}Вт) эксплуатируется в жаре (ср. темп. {data.avg_temperature}°C). Перегрев радиатора драйвера.",
            character="Постепенная деградация"
        )

    # 3. Проверка влаги и возраста (Коррозия)
    # Если старая (>7 лет) и влажно
    if data.age_years > 7 and data.avg_humidity > 70:
        return DiagnosisResult(
            likely_cause="Нарушение герметичности и коррозия",
            description="Разрушение уплотнителей корпуса из-за возраста и высокой влажности. Попадание воды на плату управления.",
            character="Химический износ"
        )

    # 4. Естественный износ ресурса
    # Если наработка близка к пределу
    life_hours_map = {'Budget': 30000, 'Standard': 50000, 'Premium': 70000}
    max_life = life_hours_map[data.quality_tier]
    
    if data.operating_hours > max_life * 0.8: # Если выработано >80% ресурса
        return DiagnosisResult(
            likely_cause="Выработка ресурса LED-кристаллов",
            description=f"Наработка {data.operating_hours} часов превышает норматив для {data.quality_tier} класса. Снижение светового потока.",
            character="Естественное старение"
        )

    # 5. Если ни один фактор не критичен, но вероятность высока (комплексный фактор)
    return DiagnosisResult(
        likely_cause="Комплексный износ оборудования",
        description="Накопленная погрешность от нескольких факторов: вибрации, микротрещины, незначительные перегревы.",
        character="Скрытый дефект"
    )

# --- 4. ENDPOINT ---

@app.post("/predict", response_model=PredictionResponse)
def predict_lamp_failure(data: LampData):
    try:
        input_dict = data.dict()
        input_dict['quality_code'] = QUALITY_MAP[input_dict['quality_tier']]
        
        features_order = [
            'power_watts', 'age_years', 'operating_hours', 
            'switching_cycles', 'voltage_spike_count', 
            'avg_humidity', 'avg_temperature', 'previous_repairs', 'quality_code'
        ]
        
        df_input = pd.DataFrame([input_dict])[features_order]
        
        prediction = model.predict(df_input)[0]
        probability = model.predict_proba(df_input)[0][1]
        
        # Формируем рекомендацию
        if probability > 0.7:
            rec = "КРИТИЧНО: Требуется срочная замена или ремонт."
        elif probability > 0.4:
            rec = "ВНИМАНИЕ: Рекомендована внеплановая диагностика."
        else:
            rec = "НОРМА: Оборудование в рабочем состоянии."

        # Получаем диагноз
        diagnosis = get_failure_diagnosis(data, probability)
            
        return PredictionResponse(
            failure_probability=round(probability, 3),
            prediction=int(prediction),
            recommendation=rec,
            diagnosis=diagnosis
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при предсказании: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
