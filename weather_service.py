import httpx
import random
import time
import os
from typing import Tuple, Optional, Dict, Any

class WeatherService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OWM_API_KEY", "b338c575afc991423bf1531a90574f21")
        self._cache: Dict[str, Any] = {"data": None, "timestamp": 0}
        self._cache_ttl = 600  # 10 minutes

    async def get_wind_data(self, lat: float, lon: float) -> Tuple[float, float]:
        """
        Получает данные о ветре (скорость, направление) по координатам.
        Использует кэширование и мок-данные при ошибке.
        """
        # Проверка кэша
        if self._cache["data"] and (time.time() - self._cache["timestamp"] < self._cache_ttl):
            print("[Weather API] Returning cached data")
            return self._cache["data"]

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat, 
            "lon": lon, 
            "appid": self.api_key, 
            "units": "metric"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=3.0)
                if response.status_code == 200:
                    data = response.json()
                    wind = data.get('wind', {})
                    speed = wind.get('speed', 0.0)
                    deg = wind.get('deg', 0.0)
                    print(f"[Weather API] Real data received: Speed={speed}, Deg={deg}")
                    
                    # Обновление кэша
                    self._cache["data"] = (speed, deg)
                    self._cache["timestamp"] = time.time()
                    return speed, deg
                else:
                    print(f"[Weather API] API Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[Weather API] Network Error: {e}")

        # Fallback to Mock Data
        print("[Weather API] Using Mock data")
        mock_speed = random.uniform(2.0, 8.0)
        mock_deg = random.uniform(0, 360)
        return mock_speed, mock_deg

# Singleton instance for simple usage if needed, 
# but preferably instantiated in main.py
default_weather_service = WeatherService()

async def get_wind_data(lat: float, lon: float) -> Tuple[float, float]:
    """Legacy wrapper for backward compatibility if needed."""
    return await default_weather_service.get_wind_data(lat, lon)
