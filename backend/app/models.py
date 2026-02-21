from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


# ── Enums ──────────────────────────────────────────────

class LampStatus(str, Enum):
    OK = "ok"
    BURNED_OUT = "burned_out"
    ABSENT = "absent"
    MAINTENANCE = "maintenance"


class DroneStatus(str, Enum):
    IDLE = "idle"
    IN_FLIGHT = "in_flight"
    CHARGING = "charging"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class JobStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Streetlight (фонарный столб / точка освещения) ─────

class Streetlight(SQLModel, table=True):
    __tablename__ = "streetlights"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)                        # "СТ-001"
    latitude: float
    longitude: float
    address: str = ""
    modbus_slave_id: int = Field(unique=True)             # 1-247
    installed_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    lamp: Optional["Lamp"] = Relationship(back_populates="streetlight")


# ── Lamp (лампочка, привязана к столбу) ────────────────

class Lamp(SQLModel, table=True):
    __tablename__ = "lamps"

    id: Optional[int] = Field(default=None, primary_key=True)
    streetlight_id: int = Field(foreign_key="streetlights.id", unique=True)

    # Статус
    status: LampStatus = LampStatus.OK
    is_on: bool = False

    # Показатели от контроллера (поля из ТЗ)
    hours_active: int = 0                    # наработка в часах
    junction_temp_avg: float = 0.0           # средняя температура перехода (°C)
    voltage_spike_count: int = 0             # счётчик скачков напряжения
    on_off_cycles: int = 0                   # кол-во циклов вкл/выкл
    humidity_avg: float = 0.0                # средний уровень влажности (%)

    # Дополнительные показатели
    voltage: float = 0.0                     # текущее напряжение (В)
    current_ma: float = 0.0                  # ток (мА)
    power_w: float = 0.0                     # мощность (Вт)
    ambient_temp: float = 0.0                # температура окружающей среды (°C)
    reflector_position: int = 0              # позиция отражателя (0 = закрыт)
    failure_probability: float = 0.0         # вероятность отказа (0-1) от AI

    last_seen: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    streetlight: Optional[Streetlight] = Relationship(back_populates="lamp")
    replacement_jobs: list["ReplacementJob"] = Relationship(back_populates="lamp")
    events: list["LampEvent"] = Relationship(back_populates="lamp")


# ── Drone (дрон) ───────────────────────────────────────

class Drone(SQLModel, table=True):
    __tablename__ = "drones"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str                                # "Дрон-01"
    model: str = ""                          # модель
    status: DroneStatus = DroneStatus.IDLE

    battery_level: float = 100.0             # %
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    total_flights: int = 0
    total_replacements: int = 0
    last_maintenance: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    replacement_jobs: list["ReplacementJob"] = Relationship(back_populates="drone")


# ── ReplacementJob (задание на замену) ─────────────────

class ReplacementJob(SQLModel, table=True):
    __tablename__ = "replacement_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    lamp_id: int = Field(foreign_key="lamps.id")
    drone_id: Optional[int] = Field(default=None, foreign_key="drones.id")

    status: JobStatus = JobStatus.PENDING
    priority: int = 3                        # 1=высокий, 5=низкий

    created_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

    lamp: Optional[Lamp] = Relationship(back_populates="replacement_jobs")
    drone: Optional[Drone] = Relationship(back_populates="replacement_jobs")


# ── LampEvent (лог событий) ───────────────────────────

class LampEvent(SQLModel, table=True):
    __tablename__ = "lamp_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    lamp_id: int = Field(foreign_key="lamps.id")
    event_type: str                          # status_change, replaced, spike, overheat
    details: Optional[str] = None            # JSON-строка с подробностями
    created_at: datetime = Field(default_factory=datetime.utcnow)

    lamp: Optional[Lamp] = Relationship(back_populates="events")
