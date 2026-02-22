"""Модуль работы с Яндекс.Погодой."""

import logging
from datetime import datetime, timezone
import httpx
from app.core.config import settings

logger = logging.getLogger("yandex_weather")

# Кэш: {date_str: data}
_cache: dict[str, dict] = {}
_cache_timestamp: datetime | None = None

async def get_yandex_data(client: httpx.AsyncClient) -> dict | None:
    """Получить данные от Яндекс.Погоды."""
    global _cache_timestamp

    if not settings.YANDEX_WEATHER_API_KEY:
        return None

    now = datetime.now(timezone.utc)
    # Кэш на 1 час
    if _cache and _cache_timestamp and (now - _cache_timestamp).total_seconds() < 3600:
        return _cache.get("data")

    try:
        resp = await client.get(
            "https://api.weather.yandex.ru/v2/forecast",
            params={
                "lat": settings.CITY_LAT,
                "lon": settings.CITY_LNG,
                "lang": "ru_RU",
                "limit": 7,
                "hours": "false",
                "extra": "false"
            },
            headers={"X-Yandex-API-Key": settings.YANDEX_WEATHER_API_KEY},
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        
        _cache["data"] = data
        _cache_timestamp = now
        logger.info("Fetched Yandex weather data")
        return data

    except Exception:
        logger.warning("Failed to fetch Yandex weather", exc_info=True)
        return _cache.get("data")

def is_yandex_condition_bad(condition: str, wind_speed: float, temp: float) -> tuple[bool, str]:
    """Определить плохую погоду по данным Яндекса."""
    reasons = []
    is_bad = False

    # https://yandex.ru/dev/weather/doc/ru/concepts/forecast-test#conditions
    bad_conditions = {
        "rain", "moderate-rain", "heavy-rain", "continuous-heavy-rain", "showers",
        "wet-snow", "light-snow", "snow", "snow-showers", "hail", "thunderstorm",
        "thunderstorm-with-rain", "thunderstorm-with-hail"
    }

    if condition in bad_conditions:
        is_bad = True
        reasons.append(f"Осадки ({condition})")

    if wind_speed > 15.0:
        is_bad = True
        reasons.append(f"Ветер {wind_speed} м/с")

    if temp < -20.0:
        is_bad = True
        reasons.append(f"Холод {temp}°C")

    return is_bad, ", ".join(reasons) if reasons else "Хорошая погода"
