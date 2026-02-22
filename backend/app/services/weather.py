"""Модуль получения данных о погоде через Open-Meteo API."""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.services.yandex_weather import get_yandex_data

logger = logging.getLogger("weather")

# Кэш: {date_str: {"is_bad": bool, "reason": str, ...}}
_cache: dict[str, dict] = {}
_cache_timestamp: datetime | None = None

# Override для тестирования
_override_enabled: bool = False
_override_is_bad: bool = False

def set_weather_override(enabled: bool, is_bad: bool = False) -> None:
    global _override_enabled, _override_is_bad
    _override_enabled = enabled
    _override_is_bad = is_bad

def get_weather_override() -> dict:
    return {"enabled": _override_enabled, "is_bad": _override_is_bad}

async def get_weather_forecast(client: httpx.AsyncClient) -> list[dict]:
    """
    Получить прогноз погоды на 7 дней.
    Возвращает список дней с флагом плохой погоды.
    """
    global _cache_timestamp

    if _override_enabled:
        result = []
        for i in range(7):
            date_str = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            result.append({
                "date": date_str,
                "is_bad_weather": _override_is_bad,
                "reason": "Тестовый режим: плохая погода" if _override_is_bad else "Тестовый режим: хорошая погода",
                "weather_code": 0,
                "temp_min": -5 if _override_is_bad else 15,
                "wind_max": 20 if _override_is_bad else 3,
            })
        return result

    if settings.YANDEX_WEATHER_API_KEY:
        try:
            from app.services.yandex_weather import get_yandex_data, is_yandex_condition_bad
            
            yandex_data = await get_yandex_data(client)
            if yandex_data and "forecasts" in yandex_data:
                result = []
                for day in yandex_data["forecasts"]:
                    date_str = day["date"]
                    day_part = day["parts"]["day_short"]
                    
                    temp = day_part["temp"]
                    wind = day_part["wind_speed"]
                    condition = day_part["condition"]
                    
                    is_bad, reason = is_yandex_condition_bad(condition, wind, temp)

                    result.append({
                        "date": date_str,
                        "is_bad_weather": is_bad,
                        "reason": reason,
                        "weather_code": 0,  # Yandex uses string conditions
                        "temp_min": temp,
                        "wind_max": wind,
                    })
                return result
        except Exception:
            logger.error("Failed to process Yandex weather data", exc_info=True)
            
    return []

async def is_weather_bad_today(client: httpx.AsyncClient) -> bool:
    """Проверить, плохая ли погода сегодня."""
    forecast = await get_weather_forecast(client)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for day in forecast:
        if day["date"] == today_str:
            return day["is_bad_weather"]
    
    return False
