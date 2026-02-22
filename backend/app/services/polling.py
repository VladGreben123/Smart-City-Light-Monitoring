import asyncio
import json
import logging
from datetime import datetime, timedelta

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.controller.base import BaseController, LampStatusCode
from app.core.database import Session
from app.models import Lamp, LampEvent, LampStatus, Streetlight
from app.services.websocket import WSManager
from app.services.daylight import is_dark_now

logger = logging.getLogger("polling")

STATUS_MAP = {
    LampStatusCode.ABSENT: LampStatus.ABSENT,
    LampStatusCode.OK: LampStatus.OK,
    LampStatusCode.BURNED_OUT: LampStatus.BURNED_OUT,
}

REPAIR_ON_DELAY_SECONDS = 0.5
_repair_delay_until: dict[int, datetime] = {}


def schedule_repair_delay(lamp_id: int) -> None:
    _repair_delay_until[lamp_id] = datetime.utcnow() + timedelta(seconds=REPAIR_ON_DELAY_SECONDS)


def is_in_repair_delay(lamp_id: int) -> bool:
    until = _repair_delay_until.get(lamp_id)
    if until is None:
        return False
    if datetime.utcnow() >= until:
        _repair_delay_until.pop(lamp_id, None)
        return False
    return True


async def _get_failure_probability(client: httpx.AsyncClient, lamp: Lamp) -> float | None:
    """Запросить вероятность отказа у AI-сервиса."""
    # TODO: Временно отключено, так как сервис AI не запущен (вызывает 502 Bad Gateway)
    # try:
    #     resp = await client.post(
    #         f"{settings.AI_SERVICE_URL}/predict",
    #         json={
    #             "hours_active": lamp.hours_active,
    #             "on_off_cycles": lamp.on_off_cycles,
    #             "avg_temp_exposure": lamp.ambient_temp,
    #             "temp_fluctuations": int(abs(lamp.junction_temp_avg - lamp.ambient_temp)),
    #             "voltage_spikes": lamp.voltage_spike_count,
    #             "humidity_exposure": lamp.humidity_avg,
    #         },
    #         timeout=2.0,
    #     )
    #     if resp.status_code == 200:
    #         return resp.json().get("failure_probability", 0.0)
    # except Exception:
    #     logger.debug("AI service unavailable, using fallback")
    return None  # AI недоступен, используем fallback логику


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
            # Симуляция хаоса (если это мок-контроллер)
            if hasattr(controller, "simulate_chaos"):
                controller.simulate_chaos()
                
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
        # Оптимизация: загружаем Streetlight сразу вместе с Lamp, чтобы избежать N+1
        # Используем join для эффективности
        results = session.exec(
            select(Streetlight, Lamp).join(Lamp, isouter=True).where(Streetlight.is_active == True)
        ).all()

        updates: list[dict] = []

        # Используем контекстный менеджер для клиента, чтобы переиспользовать соединение
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            dark = await is_dark_now(http_client)

            for sl, lamp in results:
                if lamp is None:
                    continue

                try:
                    data = await controller.read_lamp_data(sl.modbus_slave_id)
                except Exception as e:
                    logger.warning(
                        "Failed to read slave_id=%d (%s): %s",
                        sl.modbus_slave_id,
                        sl.name,
                        str(e)
                    )
                    continue

                old_status = lamp.status
                new_status = STATUS_MAP.get(data.status, LampStatus.OK)

                lamp.status = new_status
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
                if lamp.status in (LampStatus.BURNED_OUT, LampStatus.ABSENT, LampStatus.MAINTENANCE):
                    # lamp.is_on = False # User requested state depends ONLY on time
                    if lamp.status == LampStatus.BURNED_OUT:
                        lamp.failure_probability = 1.0
                    pass

                should_be_on = lamp.is_on
                if dark is not None:
                    should_be_on = dark
                    # if lamp.status in (LampStatus.BURNED_OUT, LampStatus.ABSENT, LampStatus.MAINTENANCE):
                    #     should_be_on = False
                    if is_in_repair_delay(lamp.id):
                        should_be_on = False

                    if lamp.is_on != should_be_on:
                        try:
                            await controller.write_lamp_on(
                                sl.modbus_slave_id, should_be_on
                            )
                            lamp.is_on = should_be_on
                            logger.info(
                                "Daylight control: %s lamp slave_id=%d (%s)",
                                "ON" if should_be_on else "OFF",
                                sl.modbus_slave_id,
                                sl.name,
                            )
                        except Exception as e:
                            logger.warning(
                                "Failed to switch lamp slave_id=%d: %s",
                                sl.modbus_slave_id,
                                str(e)
                            )

                # Запрос вероятности отказа от AI
                fp = await _get_failure_probability(http_client, lamp)
                if fp is not None:
                    lamp.failure_probability = fp
                else:
                    # Fallback логика:
                    # Если лампа исправна, но вероятность поломки все еще 1.0 (например, после ремонта или stale data),
                    # сбрасываем ее в 0.0
                    if lamp.status == LampStatus.OK and lamp.failure_probability >= 0.99:
                        lamp.failure_probability = 0.0

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

                # if lamp.status in (LampStatus.BURNED_OUT, LampStatus.ABSENT, LampStatus.MAINTENANCE):
                #     ws_status = "broken"
                # else:
                ws_status = "on" if lamp.is_on else "off"
                updates.append({
                    "id": lamp.id,
                    "status": ws_status,
                    "state": round(1.0 - lamp.failure_probability, 4),
                })

        session.commit()

    # Отправить каждую лампу отдельным сообщением (формат фронта)
    for upd in updates:
        await ws_manager.broadcast(upd)
