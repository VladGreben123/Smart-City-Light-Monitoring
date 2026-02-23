import logging
from fastapi import APIRouter, Depends, HTTPException, WebSocket, Request
from sqlmodel import Session, select
from pydantic import BaseModel

from app.core.database import get_session
from app.core.config import settings
from app.models import Lamp, LampStatus, Streetlight
from app.controller.base import LampStatusCode
from app.services.websocket import ws_manager
from app.services.weather import set_weather_override, get_weather_override
from app.services.yandex_weather import get_yandex_data, is_yandex_condition_bad
from app.services.routing import routing_service
import httpx
from datetime import datetime
import asyncio

# Настройка логгера
logger = logging.getLogger("api")

router = APIRouter()

# ── Lamp Management ──────────────────────────────────────

class LampUpdate(BaseModel):
    status: LampStatus

@router.patch("/lamps/{lamp_id}")
async def update_lamp_status(
    lamp_id: int,
    lamp_update: LampUpdate,
    request: Request,
    session: Session = Depends(get_session)
):
    lamp = session.get(Lamp, lamp_id)
    if not lamp:
        raise HTTPException(status_code=404, detail="Lamp not found")
    
    lamp.status = lamp_update.status
    if lamp.status == LampStatus.OK:
        lamp.failure_probability = 0.0
    
    session.add(lamp)
    session.commit()
    session.refresh(lamp)

    # Sync with controller
    try:
        if hasattr(request.app.state, "controller"):
            controller = request.app.state.controller
            if lamp.streetlight:
                slave_id = lamp.streetlight.modbus_slave_id
                code = LampStatusCode.OK
                if lamp.status == LampStatus.BURNED_OUT:
                    code = LampStatusCode.BURNED_OUT
                elif lamp.status == LampStatus.ABSENT:
                    code = LampStatusCode.ABSENT
                
                await controller.set_status(slave_id, code)
    except Exception as e:
        logger.error(f"Controller sync failed: {e}")

    return lamp

@router.get("/lamps")
async def get_lamps(session: Session = Depends(get_session)):
    statement = select(Streetlight, Lamp).join(Lamp, isouter=True)
    results = session.exec(statement).all()
    
    lamps_data = []
    for sl, lamp in results:
        lamps_data.append({
            "id": sl.id,
            "lat": sl.latitude,
            "lng": sl.longitude,
            "address": sl.address,
            "status": lamp.status if lamp else "unknown",
            "is_on": lamp.is_on if lamp else False,
            "failure_prob": lamp.failure_probability if lamp else 0.0
        })
    return lamps_data


# ── Scenario / Debugging ─────────────────────────────────

class ScenarioAction(BaseModel):
    lamp_ids: list[int]
    action: str  # "break", "fix"

@router.post("/lamps/scenario")
async def run_scenario(
    action: ScenarioAction,
    session: Session = Depends(get_session)
):
    """
    Принудительно сломать или починить лампы (для демонстрации).
    """
    lamps = session.exec(select(Lamp).where(Lamp.id.in_(action.lamp_ids))).all()
    
    for lamp in lamps:
        if action.action == "break":
            lamp.status = LampStatus.BURNED_OUT
            lamp.failure_probability = 0.99
        elif action.action == "fix":
            lamp.status = LampStatus.OK
            lamp.failure_probability = 0.05
        session.add(lamp)
    
    session.commit()
    return {"status": "ok", "updated": len(lamps)}


# ── Drone Routing (Proxy) ────────────────────────────────

@router.post("/route/optimize")
async def optimize_drone_route(session: Session = Depends(get_session)):
    """
    Получить оптимальный маршрут дрона по лампам с высокой вероятностью отказа.
    Проксирует запрос к Routing-AI (порт 8002).
    """
    logger.info("Optimize drone route requested")

    # 1. Найти лампы, которые "плохие" (сломаны или высокий риск)
    results = session.exec(
        select(Streetlight, Lamp)
        .join(Lamp, isouter=True)
        .where(
            (Lamp.failure_probability >= 0.66) |
            (Lamp.status == LampStatus.BURNED_OUT)
        )
    ).all()

    if not results:
        logger.info("No broken lamps found, returning empty route")
        return {
            "route_ids": [],
            "flight_time_minutes": 0.0,
            "savings_percent": 0.0,
            "battery_usage_percent": 0.0,
            "message": "No broken lamps to visit"
        }

    # 2. Сформировать payload для Routing-AI
    lamps_payload = [
        {"id": str(lamp.id), "lat": sl.latitude, "lng": sl.longitude}
        for sl, lamp in results
    ]

    # 3. Делегировать вызов сервису
    return await routing_service.optimize_route(
        lamps=lamps_payload,
        depot_lat=settings.CITY_LAT,
        depot_lng=settings.CITY_LNG
    )


# ── Debug / Weather override ─────────────────────────────

@router.get("/weather/forecast")
async def get_weather_forecast():
    """
    Получить прогноз погоды на 7 дней.
    Использует Яндекс.Погоду или моковые данные, если API недоступен.
    Учитывает ручной override (debug).
    """
    # 1. Проверить override
    override = get_weather_override()
    
    # 2. Получить данные от Яндекса
    yandex_data = None
    async with httpx.AsyncClient(timeout=5.0) as client:
        yandex_data = await get_yandex_data(client)
    
    forecast_list = []
    
    # Если есть данные от Яндекса
    if yandex_data and "forecasts" in yandex_data:
        for day in yandex_data["forecasts"]:
            # Обработка данных Яндекса
            date_str = day["date"]
            parts = day.get("parts", {}).get("day_short", {})
            temp = parts.get("temp", 0)
            condition = parts.get("condition", "cloudy")
            wind_speed = parts.get("wind_speed", 0)
            
            # Определяем, плохая ли погода
            is_bad, reason = is_yandex_condition_bad(condition, wind_speed, temp)
            
            # Если включен override, он имеет приоритет
            if override["enabled"]:
                is_bad = override["is_bad"]
                reason = "Ручное управление" if is_bad else "Ручное управление (OK)"

            forecast_list.append({
                "date": date_str,
                "temp": temp,
                "condition": condition,
                "wind_speed": wind_speed,
                "is_bad_weather": is_bad,
                "reason": reason
            })
    else:
        # Fallback (если нет ключа или ошибки) - генерируем заглушку на 7 дней
        base_date = datetime.now()
        for i in range(7):
            # ... простая логика генерации дат ...
            # Но лучше просто вернуть пустой список или базовый мок, 
            # чтобы фронт не падал.
            # Для простоты вернем мок на сегодня, если совсем всё плохо
            pass
            
    # Если список пуст (нет ключа и т.д.), наполним моковыми данными
    if not forecast_list:
        from datetime import timedelta
        today = datetime.now()
        for i in range(7):
            date_obj = today + timedelta(days=i)
            date_str = date_obj.strftime("%Y-%m-%d")
            
            is_bad = False
            reason = "Хорошая погода"
            
            if override["enabled"]:
                is_bad = override["is_bad"]
                reason = "Ручное управление"

            forecast_list.append({
                "date": date_str,
                "temp": 20 - i,
                "condition": "clear",
                "wind_speed": 5.0,
                "is_bad_weather": is_bad,
                "reason": reason
            })

    return forecast_list

class WeatherOverrideRequest(BaseModel):
    enabled: bool
    is_bad: bool = False

@router.post("/debug/weather-override")
async def weather_override(body: WeatherOverrideRequest):
    set_weather_override(body.enabled, body.is_bad)
    return {"ok": True, "enabled": body.enabled, "is_bad": body.is_bad}

@router.get("/debug/weather-override")
async def weather_override_status():
    return get_weather_override()


# ── WebSocket ────────────────────────────────────────────

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    logger.info("WebSocket client connected")
    try:
        while True:
            # Просто ждем сообщений, чтобы держать соединение открытым.
            # Если клиент что-то пришлет, можно обработать (например, ping).
            data = await ws.receive_text()
            # logger.debug(f"Received WS message: {data}")
    except Exception:
        # Клиент отключился
        logger.info("WebSocket client disconnected")
        ws_manager.disconnect(ws)
