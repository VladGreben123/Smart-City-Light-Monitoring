from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class LampStatusCode(int, Enum):
    ABSENT = 0
    OK = 1
    BURNED_OUT = 2


@dataclass
class LampData:
    status: LampStatusCode
    is_on: bool
    hours_active: int
    junction_temp_avg: float      # °C
    voltage_spike_count: int
    on_off_cycles: int
    humidity_avg: float           # %
    voltage: float                # В
    current_ma: float             # мА
    ambient_temp: float           # °C
    reflector_position: int       # 0 = закрыт, 180 = открыт


class BaseController(ABC):
    @abstractmethod
    async def read_lamp_data(self, slave_id: int) -> LampData:
        """Прочитать данные лампы с контроллера."""

    @abstractmethod
    async def write_lamp_on(self, slave_id: int, on: bool) -> None:
        """Включить/выключить лампу."""

    @abstractmethod
    async def write_reflector(self, slave_id: int, open: bool) -> None:
        """Открыть/закрыть отражатель для посадки дрона."""
