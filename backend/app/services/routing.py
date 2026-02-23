import logging
import math
import httpx
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger("service.routing")

class RoutingService:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def _local_fallback(self, lamps: list[dict], depot_lat: float, depot_lng: float) -> dict:
        if not lamps:
            return {
                "route_ids": [],
                "route_geometry": [[depot_lat, depot_lng], [depot_lat, depot_lng]],
                "total_energy": 0.0,
                "naive_energy": 0.0,
                "savings_percent": 0.0,
                "flight_time_minutes": 0.0,
                "battery_usage_percent": 0.0,
                "wind_speed": 0.0,
                "wind_deg": 0.0,
                "baseline_algorithm": "Nearest Neighbor (Fallback)"
            }

        remaining = lamps.copy()
        route = []
        current_lat = depot_lat
        current_lng = depot_lng

        while remaining:
            nearest = min(
                remaining,
                key=lambda l: math.dist(
                    (current_lat, current_lng),
                    (l["lat"], l["lng"]),
                ),
            )
            route.append(nearest)
            current_lat = nearest["lat"]
            current_lng = nearest["lng"]
            remaining.remove(nearest)

        geometry = [[depot_lat, depot_lng]]
        for lamp in route:
            geometry.append([lamp["lat"], lamp["lng"]])
        geometry.append([depot_lat, depot_lng])

        def deg_to_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            r = 6371000.0
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return r * c

        total_distance = 0.0
        for i in range(len(geometry) - 1):
            lat1, lon1 = geometry[i]
            lat2, lon2 = geometry[i + 1]
            total_distance += deg_to_m(lat1, lon1, lat2, lon2)

        avg_speed_mps = 10.0
        flight_time_minutes = (total_distance / avg_speed_mps) / 60.0
        battery_usage_percent = min(100.0, (total_distance / 1000.0) * 2.0)

        total_energy = total_distance

        return {
            "route_ids": [str(l["id"]) for l in route],
            "route_geometry": geometry,
            "total_energy": round(total_energy, 2),
            "naive_energy": round(total_energy, 2),
            "savings_percent": 0.0,
            "flight_time_minutes": round(flight_time_minutes, 1),
            "battery_usage_percent": round(battery_usage_percent, 1),
            "wind_speed": 0.0,
            "wind_deg": 0.0,
            "baseline_algorithm": "Nearest Neighbor (Fallback)",
        }

    async def optimize_route(self, lamps: list[dict], depot_lat: float, depot_lng: float) -> dict:
        """
        Отправляет запрос на оптимизацию маршрута во внешний сервис Routing-AI.
        """
        payload = {
            "lamps": lamps,
            "depot_lat": depot_lat,
            "depot_lng": depot_lng,
        }

        logger.info(f"Sending optimization request for {len(lamps)} lamps to {self.base_url}")
        
        try:
            async with httpx.AsyncClient(timeout=1.0, trust_env=False) as client:
                url = f"{self.base_url}/api/v1/optimize"
                resp = await client.post(url, json=payload)
                
                if resp.status_code != 200:
                    logger.error(f"Routing service error {resp.status_code}: {resp.text}")
                    # Пробрасываем ошибку с деталями от сервиса
                    raise HTTPException(
                        status_code=502,
                        detail=f"Routing service error ({resp.status_code}): {resp.text}"
                    )
                
                return resp.json()

        except httpx.TimeoutException:
            logger.error("Routing service timeout, using local fallback")
            return self._local_fallback(lamps, depot_lat, depot_lng)
        except HTTPException:
            raise
        except httpx.ConnectError:
            logger.error("Routing service connection failed (ConnectError)")
            raise HTTPException(
                status_code=503,
                detail="Smart routing service unavailable (port 8002)"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from routing service: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Routing service returned error: {e.response.text}"
            )
        except Exception as e:
            logger.exception(f"Unexpected error in routing service: {type(e).__name__} - {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal routing error: {type(e).__name__}: {str(e)}"
            )

# Singleton instance
routing_service = RoutingService(settings.ROUTING_SERVICE_URL)
