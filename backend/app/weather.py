"""Модуль получения данных о погоде через Open-Meteo API."""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings

logger = logging.getLogger("weather")

# Кэш: {date_str: {"is_bad": bool, "reason": str, ...}}
_cache: dict[str, dict] = {}
_cache_timestamp: datetime | None = None

async def get_weather_forecast(client: httpx.AsyncClient) -> list[dict]:
    """
    Получить прогноз погоды на 7 дней.
    Возвращает список дней с флагом плохой погоды.
    """
    global _cache_timestamp

    # Простая проверка кэша (валиден 1 час)
    now = datetime.now(timezone.utc)
    if _cache and _cache_timestamp and (now - _cache_timestamp).total_seconds() < 3600:
        return list(_cache.values())

    try:
        # Запрос к Open-Meteo
        # daily=weather_code,wind_speed_10m_max,temperature_2m_min
        resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": settings.CITY_LAT,
                "longitude": settings.CITY_LNG,
                "daily": "weather_code,wind_speed_10m_max,temperature_2m_min",
                "timezone": "auto",
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        
        if "daily" not in data:
            logger.warning("Unexpected weather response: %s", data)
            return []

        daily = data["daily"]
        dates = daily.get("time", [])
        codes = daily.get("weather_code", [])
        winds = daily.get("wind_speed_10m_max", [])
        temps = daily.get("temperature_2m_min", [])

        result = []
        _cache.clear()

        for i, date_str in enumerate(dates):
            code = codes[i] if i < len(codes) else 0
            wind = winds[i] if i < len(winds) else 0.0
            temp = temps[i] if i < len(temps) else 0.0

            is_bad = False
            reasons = []

            # Интерпретация кодов WMO
            # Дождь, снег, гроза - это коды >= 51 (кроме тумана 45, 48)
            # 51-55: Морось
            # 56-57: Замерзающая морось
            # 61-65: Дождь
            # 66-67: Ледяной дождь
            # 71-77: Снег
            # 80-82: Ливни
            # 85-86: Снежные ливни
            # 95-99: Гроза
            if code >= 51: 
                is_bad = True
                reasons.append("Осадки")
            
            # Ветер > 15 м/с (54 км/ч)
            if wind > 15.0:
                is_bad = True
                reasons.append(f"Ветер {wind} м/с")
            
            # Температура < -20
            if temp < -20.0:
                is_bad = True
                reasons.append(f"Холод {temp}°C")

            day_data = {
                "date": date_str,
                "is_bad_weather": is_bad,
                "reason": ", ".join(reasons) if reasons else "Хорошая погода",
                "weather_code": code,
                "temp_min": temp,
                "wind_max": wind,
            }
            result.append(day_data)
            _cache[date_str] = day_data

        _cache_timestamp = now
        logger.info("Fetched weather forecast for %d days", len(result))
        return result

    except Exception:
        logger.warning("Failed to fetch weather", exc_info=True)
        # Если есть старый кэш, вернем его, даже если протух
        if _cache:
            return list(_cache.values())
        return []

async def is_weather_bad_today(client: httpx.AsyncClient) -> bool:
    """Проверить, плохая ли погода сегодня."""
    forecast = await get_weather_forecast(client)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for day in forecast:
        if day["date"] == today_str:
            return day["is_bad_weather"]
    
    return False
