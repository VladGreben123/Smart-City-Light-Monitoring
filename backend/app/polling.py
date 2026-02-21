import asyncio
import json
import logging
from datetime import datetime

import httpx
from sqlmodel import Session, select

from app.config import settings
from app.controller.base import BaseController, LampStatusCode
from app.daylight import is_dark_now
from app.models import Lamp, LampEvent, LampStatus, Streetlight
from app.ws import WSManager

logger = logging.getLogger("polling")

STATUS_MAP = {
    LampStatusCode.ABSENT: LampStatus.ABSENT,
    LampStatusCode.OK: LampStatus.OK,
    LampStatusCode.BURNED_OUT: LampStatus.BURNED_OUT,
}


async def _get_failure_probability(client: httpx.AsyncClient, lamp: Lamp) -> float:
    """Запросить вероятность отказа у AI-сервиса."""
    try:
        resp = await client.post(
            f"{settings.AI_SERVICE_URL}/predict",
            json={
                "hours_active": lamp.hours_active,
                "on_off_cycles": lamp.on_off_cycles,
                "avg_temp_exposure": lamp.ambient_temp,
                "temp_fluctuations": int(abs(lamp.junction_temp_avg - lamp.ambient_temp)),
                "voltage_spikes": lamp.voltage_spike_count,
                "humidity_exposure": lamp.humidity_avg,
            },
            timeout=2.0,
        )
        if resp.status_code == 200:
            return resp.json().get("failure_probability", 0.0)
    except Exception:
        logger.debug("AI service unavailable, using fallback")
    return lamp.failure_probability  # оставить прежнее значение


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

        async with httpx.AsyncClient() as http_client:
            # Определить: сейчас темно или светло?
            dark = await is_dark_now(http_client)

            for sl in streetlights:
                lamp = session.exec(
                    select(Lamp).where(Lamp.streetlight_id == sl.id)
                ).first()
                if lamp is None:
                    continue

                # Управление вкл/выкл по рассвету/закату
                if dark is not None:
                    should_be_on = dark
                    if lamp.is_on != should_be_on and lamp.status != LampStatus.BURNED_OUT:
                        try:
                            await controller.write_lamp_on(
                                sl.modbus_slave_id, should_be_on
                            )
                            logger.info(
                                "Daylight control: %s lamp slave_id=%d (%s)",
                                "ON" if should_be_on else "OFF",
                                sl.modbus_slave_id,
                                sl.name,
                            )
                        except Exception:
                            logger.warning(
                                "Failed to switch lamp slave_id=%d",
                                sl.modbus_slave_id,
                            )

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

                # Запрос вероятности отказа от AI
                lamp.failure_probability = await _get_failure_probability(
                    http_client, lamp
                )

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
                    "Polled slave_id=%d is_on=%s fp=%.2f",
                    sl.modbus_slave_id,
                    data.is_on,
                    lamp.failure_probability,
                )

                updates.append({
                    "id": lamp.id,
                    "is_on": lamp.is_on,
                    "failure_probability": round(lamp.failure_probability, 4),
                })

        session.commit()

    if updates:
        await ws_manager.broadcast({"type": "update", "lamps": updates})
