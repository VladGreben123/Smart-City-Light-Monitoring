import asyncio
import json
import logging
from datetime import datetime

from sqlmodel import Session, select

from app.config import settings
from app.controller.base import BaseController, LampStatusCode
from app.models import Lamp, LampEvent, LampStatus, Streetlight
from app.ws import WSManager

logger = logging.getLogger("polling")

STATUS_MAP = {
    LampStatusCode.ABSENT: LampStatus.ABSENT,
    LampStatusCode.OK: LampStatus.OK,
    LampStatusCode.BURNED_OUT: LampStatus.BURNED_OUT,
}


async def polling_loop(
    controller: BaseController,
    engine,
    ws_manager: WSManager,
) -> None:
    """Фоновый цикл опроса контроллеров каждые POLL_INTERVAL секунд."""
    logger.info(
        "Polling loop started (mode=%s, interval=%ds)",
        settings.CONTROLLER_MODE,
        settings.POLL_INTERVAL,
    )

    while True:
        try:
            await _poll_once(controller, engine, ws_manager)
        except Exception:
            logger.exception("Polling cycle error")
        await asyncio.sleep(settings.POLL_INTERVAL)


async def _poll_once(
    controller: BaseController,
    engine,
    ws_manager: WSManager,
) -> None:
    with Session(engine) as session:
        streetlights = session.exec(
            select(Streetlight).where(Streetlight.is_active == True)
        ).all()

        updates: list[dict] = []

        for sl in streetlights:
            lamp = session.exec(
                select(Lamp).where(Lamp.streetlight_id == sl.id)
            ).first()
            if lamp is None:
                continue

            try:
                data = await controller.read_lamp_data(sl.modbus_slave_id)
            except Exception:
                logger.warning(
                    "Failed to read slave_id=%d (%s)",
                    sl.modbus_slave_id,
                    sl.name,
                )
                continue

            old_status = lamp.status
            new_status = STATUS_MAP.get(data.status, LampStatus.OK)

            lamp.status = new_status
            lamp.is_on = data.is_on
            lamp.hours_active = data.hours_active
            lamp.junction_temp_avg = data.junction_temp_avg
            lamp.voltage_spike_count = data.voltage_spike_count
            lamp.on_off_cycles = data.on_off_cycles
            lamp.humidity_avg = data.humidity_avg
            lamp.voltage = data.voltage
            lamp.current_ma = data.current_ma
            lamp.power_w = round(data.voltage * data.current_ma / 1000.0, 2)
            lamp.ambient_temp = data.ambient_temp
            lamp.reflector_position = data.reflector_position
            lamp.last_seen = datetime.utcnow()
            lamp.updated_at = datetime.utcnow()

            # Запись события при смене статуса
            if old_status != new_status:
                event = LampEvent(
                    lamp_id=lamp.id,
                    event_type="status_change",
                    details=json.dumps({
                        "from": old_status.value,
                        "to": new_status.value,
                    }),
                )
                session.add(event)
                logger.info(
                    "Lamp %d status: %s -> %s",
                    lamp.id,
                    old_status.value,
                    new_status.value,
                )

            logger.debug(
                "Polled slave_id=%d status=%s temp=%.1f voltage=%.1f",
                sl.modbus_slave_id,
                new_status.value,
                data.junction_temp_avg,
                data.voltage,
            )

            updates.append({
                "streetlight_id": sl.id,
                "lamp_id": lamp.id,
                "name": sl.name,
                "latitude": sl.latitude,
                "longitude": sl.longitude,
                "status": new_status.value,
                "is_on": data.is_on,
                "voltage": data.voltage,
                "current_ma": data.current_ma,
                "junction_temp_avg": data.junction_temp_avg,
                "ambient_temp": data.ambient_temp,
                "humidity_avg": data.humidity_avg,
                "hours_active": data.hours_active,
                "reflector_position": data.reflector_position,
            })

        session.commit()

    if updates:
        await ws_manager.broadcast({"type": "lamp_update", "lamps": updates})
