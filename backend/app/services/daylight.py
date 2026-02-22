"""Модуль определения светлого/тёмного времени суток через sunrise-sunset.org API."""

import logging
from datetime import datetime, timezone

import httpx


from app.core.config import settings

logger = logging.getLogger("daylight")

# Кэш на сутки: {date_str: (sunrise_utc, sunset_utc)}
_cache: dict[str, tuple[datetime, datetime]] = {}


async def _fetch_sun_times(client: httpx.AsyncClient) -> tuple[datetime, datetime] | None:
    """Получить sunrise/sunset UTC от API."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if today in _cache:
        return _cache[today]

    if settings.YANDEX_WEATHER_API_KEY:
        try:
            from app.services.yandex_weather import get_yandex_data
            from datetime import timedelta
            
            yandex_data = await get_yandex_data(client)
            if yandex_data and "forecasts" in yandex_data:
                # Находим прогноз на сегодня
                today_forecast = None
                for f in yandex_data["forecasts"]:
                    if f["date"] == today:
                        today_forecast = f
                        break
                
                if today_forecast:
                    # offset в секундах от UTC
                    offset_sec = yandex_data.get("info", {}).get("tzinfo", {}).get("offset", 10800)
                    offset = timedelta(seconds=offset_sec)
                    
                    # Парсим время восхода/заката (HH:MM локальное время)
                    sunrise_str = today_forecast.get("sunrise")
                    sunset_str = today_forecast.get("sunset")
                    
                    if sunrise_str and sunset_str:
                        # Формируем локальный datetime
                        sunrise_local = datetime.fromisoformat(f"{today}T{sunrise_str}:00")
                        sunset_local = datetime.fromisoformat(f"{today}T{sunset_str}:00")
                        
                        # Переводим в UTC
                        # Локальное время = UTC + offset  =>  UTC = Локальное - offset
                        # Но datetime не имеет timezone info по умолчанию.
                        # Лучше задать timezone info для локального и сконвертировать в UTC
                        
                        tz = timezone(offset)
                        sunrise = sunrise_local.replace(tzinfo=tz).astimezone(timezone.utc)
                        sunset = sunset_local.replace(tzinfo=tz).astimezone(timezone.utc)
                        
                        _cache.clear()
                        _cache[today] = (sunrise, sunset)
                        logger.info("Yandex Sun times for %s: sunrise=%s sunset=%s", today, sunrise, sunset)
                        return sunrise, sunset
        except Exception:
            logger.error("Failed to fetch sun times from Yandex", exc_info=True)
            
    return None


async def is_dark_now(client: httpx.AsyncClient) -> bool | None:
    """Определить, тёмное ли сейчас время суток. None если данные недоступны."""
    times = await _fetch_sun_times(client)
    if times is None:
        return None

    sunrise, sunset = times
    now = datetime.now(timezone.utc)
    # Тёмное время: до рассвета или после заката
    return now < sunrise or now > sunset
