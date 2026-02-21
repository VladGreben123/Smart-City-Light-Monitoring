"""Модуль определения светлого/тёмного времени суток через sunrise-sunset.org API."""

import logging
from datetime import datetime, timezone

import httpx


from app.config import settings

logger = logging.getLogger("daylight")

# Кэш на сутки: {date_str: (sunrise_utc, sunset_utc)}
_cache: dict[str, tuple[datetime, datetime]] = {}


async def _fetch_sun_times(client: httpx.AsyncClient) -> tuple[datetime, datetime] | None:
    """Получить sunrise/sunset UTC от API."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if today in _cache:
        return _cache[today]

    try:
        resp = await client.get(
            "https://api.sunrise-sunset.org/json",
            params={
                "lat": settings.CITY_LAT,
                "lng": settings.CITY_LNG,
                "formatted": 0,
                "date": "today",
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK" or "results" not in data:
            logger.warning("Unexpected sunrise-sunset response: %s", data)
            return None

        sunrise_raw = data["results"].get("sunrise")
        sunset_raw = data["results"].get("sunset")
        if not sunrise_raw or not sunset_raw:
            logger.warning("Missing sunrise/sunset in response: %s", data)
            return None

        sunrise = datetime.fromisoformat(sunrise_raw)
        sunset = datetime.fromisoformat(sunset_raw)

        # Очистить старый кэш, сохранить новый
        _cache.clear()
        _cache[today] = (sunrise, sunset)

        logger.info("Sun times for %s: sunrise=%s sunset=%s", today, sunrise, sunset)
        return sunrise, sunset

    except Exception:
        logger.warning("Failed to fetch sun times", exc_info=True)
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
