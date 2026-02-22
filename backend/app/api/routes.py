from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select
import json
import logging
import httpx

from app.core.database import get_session, engine
from app.models import Lamp, LampEvent, LampStatus, Streetlight
from app.controller.base import LampStatusCode
from app.services.websocket import ws_manager
from app.services.weather import get_weather_forecast, is_weather_bad_today
from app.services.polling import schedule_repair_delay

logger = logging.getLogger("api")
router = APIRouter()

def _lamp_ws_status(lamp: Lamp) -> str:
    """Маппинг внутреннего статуса лампы в формат фронтенда."""
    return "on" if lamp.is_on else "off"

# ── REST API ─────────────────────────────────────────────

@router.get("/lamps")
def get_lamps(session: Session = Depends(get_session)):
    """Все лампы с координатами столбов."""
    results = session.exec(
        select(Streetlight, Lamp).join(Lamp, isouter=True)
    ).all()

    out = []
    for sl, lamp in results:
        item = {
            "streetlight_id": sl.id,
            "name": sl.name,
            "latitude": sl.latitude,
            "longitude": sl.longitude,
            "address": sl.address,
            "is_active": sl.is_active,
        }
        if lamp:
            item.update({
                "lamp_id": lamp.id,
                "status": lamp.status.value,
                "is_on": lamp.is_on,
                "failure_probability": lamp.failure_probability,
                "voltage": lamp.voltage,
                "current_ma": lamp.current_ma,
                "power_w": lamp.power_w,
                "junction_temp_avg": lamp.junction_temp_avg,
                "ambient_temp": lamp.ambient_temp,
                "humidity_avg": lamp.humidity_avg,
                "hours_active": lamp.hours_active,
                "voltage_spike_count": lamp.voltage_spike_count,
                "on_off_cycles": lamp.on_off_cycles,
                "reflector_position": lamp.reflector_position,
                "last_seen": lamp.last_seen,
            })
        out.append(item)
    return out


@router.get("/lamps/{lamp_id}")
def get_lamp(lamp_id: int, session: Session = Depends(get_session)):
    lamp = session.get(Lamp, lamp_id)
    if not lamp:
        raise HTTPException(404, "Lamp not found")
    sl = session.get(Streetlight, lamp.streetlight_id)
    return {
        "lamp_id": lamp.id,
        "streetlight_id": sl.id,
        "name": sl.name,
        "latitude": sl.latitude,
        "longitude": sl.longitude,
        "address": sl.address,
        "status": lamp.status.value,
        "is_on": lamp.is_on,
        "failure_probability": lamp.failure_probability,
        "voltage": lamp.voltage,
        "current_ma": lamp.current_ma,
        "power_w": lamp.power_w,
        "junction_temp_avg": lamp.junction_temp_avg,
        "ambient_temp": lamp.ambient_temp,
        "humidity_avg": lamp.humidity_avg,
        "hours_active": lamp.hours_active,
        "voltage_spike_count": lamp.voltage_spike_count,
        "on_off_cycles": lamp.on_off_cycles,
        "reflector_position": lamp.reflector_position,
        "last_seen": lamp.last_seen,
        "updated_at": lamp.updated_at,
    }


@router.get("/lamps/{lamp_id}/events")
def get_lamp_events(lamp_id: int, session: Session = Depends(get_session)):
    events = session.exec(
        select(LampEvent)
        .where(LampEvent.lamp_id == lamp_id)
        .order_by(LampEvent.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "details": e.details,
            "created_at": e.created_at,
        }
        for e in events
    ]


# ── Weather API ──────────────────────────────────────────

@router.get("/weather/forecast")
async def get_forecast():
    """Получить прогноз погоды на 7 дней."""
    async with httpx.AsyncClient() as client:
        return await get_weather_forecast(client)

@router.get("/weather/today")
async def get_today_weather():
    """Узнать, плохая ли погода сегодня."""
    async with httpx.AsyncClient() as client:
        is_bad = await is_weather_bad_today(client)
        return {"is_bad_weather": is_bad}


# ── WebSocket ────────────────────────────────────────────

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    logger.info("WebSocket client connected")

    # Отправить начальное состояние каждой лампы отдельным сообщением
    with Session(engine) as session:
        results = session.exec(
            select(Streetlight, Lamp).join(Lamp, isouter=True)
        ).all()
        for sl, lamp in results:
            if lamp is None:
                continue
            msg = {
                "id": lamp.id,
                "status": _lamp_ws_status(lamp),
                "state": round(1.0 - lamp.failure_probability, 4),
                "lat": sl.latitude,
                "lng": sl.longitude,
                "address": sl.address,
            }
            await ws.send_text(json.dumps(msg, ensure_ascii=False))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            lamp_id = msg.get("id")
            if lamp_id is None:
                continue

            new_status = msg.get("status")
            new_state = msg.get("state")

            # Обработка сообщения от дрона: {id, state} (ремонт)
            if new_state is not None:
                with Session(engine) as session:
                    lamp = session.get(Lamp, lamp_id)
                    if not lamp:
                        continue
                    sl = session.get(Streetlight, lamp.streetlight_id)
                    
                    # Нам нужен controller. Доступ к нему через app.state сложно получить внутри роутера без request.
                    # Но WebSocket endpoint имеет доступ к app через ws.app
                    controller = ws.app.state.controller

                    old_status = lamp.status
                    lamp.failure_probability = round(1.0 - float(new_state), 4)
                    if float(new_state) >= 0.66:
                        lamp.status = LampStatus.OK
                        await controller.set_status(sl.modbus_slave_id, LampStatusCode.OK)
                    lamp.is_on = False
                    schedule_repair_delay(lamp.id)
                    event = LampEvent(
                        lamp_id=lamp.id,
                        event_type="replaced",
                        details=json.dumps({
                            "from": old_status.value,
                            "to": lamp.status.value,
                        }),
                    )
                    session.add(event)
                    session.commit()
                    session.refresh(lamp) 

                    await ws_manager.broadcast(
                        {
                            "id": lamp.id,
                            "status": _lamp_ws_status(lamp),
                            "state": round(float(new_state), 4),
                        },
                        exclude=ws,
                    )
                continue

    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
        logger.info("WebSocket client disconnected")
