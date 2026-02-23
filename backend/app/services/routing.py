import logging
import httpx
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger("service.routing")

class RoutingService:
    def __init__(self, base_url: str):
        self.base_url = base_url

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
            # trust_env=False чтобы игнорировать прокси для локальных запросов
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
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

        except HTTPException:
            raise  # Пробрасываем уже сформированные исключения
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
            logger.exception("Unexpected error in routing service")
            raise HTTPException(
                status_code=500,
                detail=f"Internal routing error: {str(e)}"
            )

# Singleton instance
routing_service = RoutingService(settings.ROUTING_SERVICE_URL)
