import asyncio
import json
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.controller import get_controller
from app.core.database import create_db, engine, get_session
from app.models import Lamp, LampEvent, Streetlight
from app.services.polling import polling_loop
from app.services.websocket import ws_manager
from app.api.routes import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
)
logger = logging.getLogger("main")


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

app.include_router(api_router, prefix="/api")

# ── Demo seed ────────────────────────────────────────────

def _generate_lamp_positions() -> list[tuple[str, float, float, str]]:
    """Генерация позиций ламп."""
    ORIGIN_LAT = settings.CITY_LAT
    ORIGIN_LNG = settings.CITY_LNG

    lamps: list[tuple[str, float, float, str]] = []

    for i in range(settings.LAMP_COUNT):
        lamps.append((
            f"Universitetskaya St #{i+1}",
            ORIGIN_LAT - i * 0.00035,
            ORIGIN_LNG - i * 0.0002,
            f"Universitetskaya St #{i+1}",
        ))

    return lamps


def _seed_demo_data() -> None:
    """Создать демо-данные, если БД пуста или не соответствует ожидаемому размеру."""
    with Session(engine) as session:
        streetlights = session.exec(select(Streetlight)).all()
        lamps = session.exec(select(Lamp)).all()
        if len(streetlights) == settings.LAMP_COUNT and len(lamps) == settings.LAMP_COUNT:
            return

        if streetlights or lamps:
            session.exec(delete(LampEvent))
            session.exec(delete(Lamp))
            session.exec(delete(Streetlight))
            session.commit()

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

            lamp = Lamp(streetlight_id=sl.id, is_on=False)
            session.add(lamp)

        session.commit()
        logger.info("Seeded %d demo streetlights", len(positions))


# ── REST API ─────────────────────────────────────────────

# ── Demo seed ────────────────────────────────────────────
