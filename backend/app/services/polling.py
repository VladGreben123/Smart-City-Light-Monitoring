import asyncio
import json
import logging
import random
from datetime import datetime, timedelta

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.controller.base import BaseController, LampStatusCode
from app.models import Lamp, LampEvent, LampStatus, Streetlight
from app.services.websocket import WSManager
from app.services.daylight import is_dark_now

logger = logging.getLogger("polling")

# Suppress httpx info logs to avoid 502 spam if AI service is down
logging.getLogger("httpx").setLevel(logging.WARNING)

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


def _calculate_mock_failure_probability(lamp: Lamp) -> float:
    """Mock calculation if AI service is unavailable."""
    # Base probability
    prob = 0.01
    
    # Age factor (e.g. 1% per year)
    age_years = (lamp.hours_active or 0) / 8760
    prob += age_years * 0.01
    
    # Voltage spikes (high impact)
    if lamp.voltage_spike_count:
        prob += lamp.voltage_spike_count * 0.05
        
    # Temperature stress
    if lamp.junction_temp_avg and lamp.junction_temp_avg > 80:
        prob += 0.1
        
    return min(0.95, max(0.0, prob))


async def _get_failure_probability(client: httpx.AsyncClient, lamp: Lamp) -> float | None:
    """Запросить вероятность отказа у AI-сервиса (AI, port 8001)."""
    try:
        age_years = round(lamp.hours_active / 8760, 2) if lamp.hours_active else 0.0
        power_w = int(lamp.power_w) if lamp.power_w else 100
        
        # Check if we should even try (optimization)
        # If we failed recently, maybe skip? For now, just try.
        
        resp = await client.post(
            f"{settings.AI_PREDICT_URL}/predict",
            json={
                "power_watts": power_w,
                "quality_tier": "Standard",
                "age_years": age_years,
                "operating_hours": lamp.hours_active,
                "switching_cycles": lamp.on_off_cycles,
                "voltage_spike_count": lamp.voltage_spike_count,
                "avg_humidity": lamp.humidity_avg,
                "avg_temperature": lamp.ambient_temp,
                "previous_repairs": 0,
            },
            timeout=1.0, # Reduced timeout for faster fallback
        )
        if resp.status_code == 200:
            return resp.json().get("failure_probability", 0.0)
        else:
             # If service exists but errors (e.g. 500 or 502), use fallback
             logger.debug(f"AI service returned {resp.status_code}, using fallback")
             return _calculate_mock_failure_probability(lamp)
             
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
        # Service down or unreachable
        logger.debug("AI predict service unavailable, using fallback")
        return _calculate_mock_failure_probability(lamp)
    except Exception as e:
        logger.warning(f"Unexpected error in AI prediction: {e}")
        return _calculate_mock_failure_probability(lamp)
    
    return None


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
            # Симуляция хаоса (если это MockController)
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
        results = session.exec(
            select(Streetlight, Lamp).join(Lamp, isouter=True).where(Streetlight.is_active == True)
        ).all()

        # Используем контекстный менеджер для клиента, чтобы переиспользовать соединение
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as http_client:
            dark = await is_dark_now(http_client)
            if dark is None:
                hour = datetime.now().hour
                dark = hour >= 20 or hour < 6

            # 1. Сбор данных с контроллеров (последовательно, т.к. Modbus часто требует последовательности)
            processed_entries = []
            ai_tasks = []
            
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
                
                # Сохраняем старый статус для сравнения
                old_status = lamp.status
                
                # Обновляем поля из контроллера
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
                    if lamp.status == LampStatus.BURNED_OUT:
                        lamp.failure_probability = 1.0

                should_be_on = dark
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
                        logger.warning("Failed to switch lamp slave_id=%d: %s", sl.modbus_slave_id, str(e))

                # Добавляем в список для AI-запроса
                processed_entries.append((sl, lamp, old_status))
                ai_tasks.append(_get_failure_probability(http_client, lamp))

            # 2. Параллельный запрос к AI
            ai_results = await asyncio.gather(*ai_tasks, return_exceptions=True)

            # 3. Применение результатов AI и отправка обновлений
            for i, (sl, lamp, old_status) in enumerate(processed_entries):
                fp = ai_results[i]
                
                if isinstance(fp, Exception):
                    logger.warning(f"AI prediction failed for lamp {lamp.id}: {fp}")
                    fp = None
                
                if fp is not None:
                    lamp.failure_probability = fp
                else:
                    # Fallback
                    if lamp.status == LampStatus.OK and lamp.failure_probability >= 0.99:
                        lamp.failure_probability = 0.0

                # Запись события при смене статуса
                if old_status != lamp.status:
                    event = LampEvent(
                        lamp_id=lamp.id,
                        event_type="status_change",
                        details=json.dumps({
                            "from": old_status.value,
                            "to": lamp.status.value,
                        }),
                    )
                    session.add(event)
                    logger.info(
                        "Lamp %d status: %s -> %s",
                        lamp.id,
                        old_status.value,
                        lamp.status.value,
                    )
                
                # МГНОВЕННАЯ отправка обновления по WebSocket
                update_payload = {
                    "id": lamp.id,
                    "status": lamp.status.value,
                    "is_on": lamp.is_on,
                    "state": round(1.0 - lamp.failure_probability, 4),
                }
                await ws_manager.broadcast(update_payload)

        session.commit()
