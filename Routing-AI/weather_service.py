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
        if self._cache["data"] and (time.time() - self._cache["timestamp"] < self._cache_ttl):
            print("[Weather API] Returning cached data")
            return self._cache["data"]

        mock_speed = random.uniform(2.0, 8.0)
        mock_deg = random.uniform(0, 360)
        print(f"[Weather API] Using Mock data: Speed={mock_speed}, Deg={mock_deg}")
        self._cache["data"] = (mock_speed, mock_deg)
        self._cache["timestamp"] = time.time()
        return mock_speed, mock_deg

# Singleton instance for simple usage if needed, 
# but preferably instantiated in main.py
default_weather_service = WeatherService()


