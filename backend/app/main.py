import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.controller import get_controller
from app.controller.base import LampStatusCode
from app.database import create_db, engine, get_session
from app.models import Lamp, LampEvent, LampStatus, Streetlight
from app.polling import polling_loop
from app.ws import WSManager


def _lamp_ws_status(lamp: Lamp) -> str:
    """Маппинг внутреннего статуса лампы в формат фронтенда."""
    if lamp.status in (LampStatus.BURNED_OUT, LampStatus.ABSENT, LampStatus.MAINTENANCE):
        return "broken"
    return "on" if lamp.is_on else "off"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
)
logger = logging.getLogger("main")

ws_manager = WSManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    _seed_demo_data()

    controller = get_controller()
    app.state.controller = controller
    task = asyncio.create_task(polling_loop(controller, engine, ws_manager))
    logger.info("App started, polling task created")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Smart Streetlight API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Demo seed ────────────────────────────────────────────

def _generate_lamp_positions() -> list[tuple[str, float, float, str]]:
    """Генерация позиций ламп — зеркалит логику generateLamps() на фронте."""
    ORIGIN_LAT = 55.752317
    ORIGIN_LNG = 48.744578
    import math

    lamps: list[tuple[str, float, float, str]] = []

    # 1. Universitetskaya St (15 ламп)
    for i in range(15):
        lamps.append((
            f"Universitetskaya St #{i+1}",
            ORIGIN_LAT - i * 0.0004,
            ORIGIN_LNG - i * 0.0002,
            f"Universitetskaya St #{i+1}",
        ))

    # 2. Sportivnaya St (15 ламп)
    for i in range(15):
        lamps.append((
            f"Sportivnaya St #{i+1}",
            ORIGIN_LAT - i * 0.0001,
            ORIGIN_LNG + i * 0.0005,
            f"Sportivnaya St #{i+1}",
        ))

    # 3. Central Park Ring (12 ламп)
    park_lat, park_lng, radius = 55.7510, 48.7480, 0.0015
    for i in range(12):
        angle = (i / 12) * 2 * math.pi
        lamps.append((
            f"Central Park #{i+1}",
            park_lat + radius * math.cos(angle) * 0.6,
            park_lng + radius * math.sin(angle),
            f"Central Park #{i+1}",
        ))

    # 4. Technopark Loop (10 ламп)
    techno_lat, techno_lng = 55.751817, 48.742578
    for i in range(10):
        lamps.append((
            f"Technopark Loop #{i+1}",
            techno_lat + i * 0.0003,
            techno_lng - i * 0.0001,
            f"Technopark Loop #{i+1}",
        ))

    # 5. Residential District (10 ламп)
    res_lat, res_lng = 55.754817, 48.746578
    for i in range(10):
        lamps.append((
            f"Residential District #{i+1}",
            res_lat - i * 0.0002,
            res_lng + i * 0.0004,
            f"Residential District #{i+1}",
        ))

    return lamps


def _seed_demo_data() -> None:
    """Создать демо-данные, если БД пуста."""
    with Session(engine) as session:
        existing = session.exec(select(Streetlight)).first()
        if existing:
            return

        positions = _generate_lamp_positions()

        for idx, (name, lat, lon, addr) in enumerate(positions, start=1):
            sl = Streetlight(
                name=name,
                latitude=lat,
                longitude=lon,
                address=addr,
                modbus_slave_id=idx,
            )
            session.add(sl)
            session.flush()

            lamp = Lamp(streetlight_id=sl.id, is_on=True)
            session.add(lamp)

        session.commit()
        logger.info("Seeded %d demo streetlights", len(positions))


# ── REST API ─────────────────────────────────────────────

@app.get("/api/lamps")
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


@app.get("/api/lamps/{lamp_id}")
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


@app.get("/api/lamps/{lamp_id}/events")
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


# ── WebSocket ────────────────────────────────────────────

@app.websocket("/ws")
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

            # Обработка сообщения от дрона: {id, state} (без status)
            if new_state is not None and new_status is None:
                with Session(engine) as session:
                    lamp = session.get(Lamp, lamp_id)
                    if not lamp:
                        continue
                    sl = session.get(Streetlight, lamp.streetlight_id)
                    controller = app.state.controller

                    # state=1 означает "починено" → failure_probability=0, статус OK
                    lamp.failure_probability = round(1.0 - float(new_state), 4)
                    if float(new_state) >= 0.66:
                        lamp.status = LampStatus.OK
                        await controller.set_status(sl.modbus_slave_id, LampStatusCode.OK)
                    session.commit()

                    await ws_manager.broadcast(
                        {"id": lamp.id, "state": round(float(new_state), 4)},
                        exclude=ws,
                    )
                continue

            if new_status not in ("on", "off", "broken"):
                continue

            with Session(engine) as session:
                lamp = session.get(Lamp, lamp_id)
                if not lamp:
                    continue

                sl = session.get(Streetlight, lamp.streetlight_id)
                controller = app.state.controller

                if new_status == "broken":
                    lamp.status = LampStatus.BURNED_OUT
                    lamp.is_on = False
                    await controller.set_status(sl.modbus_slave_id, LampStatusCode.BURNED_OUT)
                elif new_status == "on":
                    lamp.status = LampStatus.OK
                    lamp.is_on = True
                    await controller.set_status(sl.modbus_slave_id, LampStatusCode.OK)
                    await controller.write_lamp_on(sl.modbus_slave_id, True)
                else:  # "off"
                    if lamp.status == LampStatus.BURNED_OUT:
                        lamp.status = LampStatus.OK
                        await controller.set_status(sl.modbus_slave_id, LampStatusCode.OK)
                    lamp.is_on = False
                    await controller.write_lamp_on(sl.modbus_slave_id, False)
                session.commit()

                # Отправить обновление всем остальным клиентам
                await ws_manager.broadcast(
                    {
                        "id": lamp.id,
                        "status": new_status,
                        "state": round(1.0 - lamp.failure_probability, 4),
                    },
                    exclude=ws,
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
        logger.info("WebSocket client disconnected")
