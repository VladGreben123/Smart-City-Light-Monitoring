import random
from dataclasses import dataclass, field

from app.controller.base import BaseController, LampData, LampStatusCode


@dataclass
class _MockLampState:
    """Внутреннее состояние мок-лампы."""
    status: LampStatusCode = LampStatusCode.OK
    is_on: bool = True
    hours_active: int = 0
    junction_temp_avg: float = 45.0
    voltage_spike_count: int = 0
    on_off_cycles: int = 0
    humidity_avg: float = 55.0
    voltage: float = 220.0
    current_ma: float = 350.0
    ambient_temp: float = 20.0
    reflector_position: int = 0  # 0=закрыт


class MockController(BaseController):
    """Мок-контроллер: генерирует реалистичные данные без реального RS485."""

    def __init__(self) -> None:
        self._states: dict[int, _MockLampState] = {}

    def _get_state(self, slave_id: int) -> _MockLampState:
        if slave_id not in self._states:
            self._states[slave_id] = _MockLampState(
                hours_active=random.randint(100, 5000),
                junction_temp_avg=random.uniform(35.0, 55.0),
                voltage_spike_count=random.randint(0, 20),
                on_off_cycles=random.randint(50, 500),
                humidity_avg=random.uniform(30.0, 70.0),
                ambient_temp=random.uniform(-10.0, 30.0),
            )
        return self._states[slave_id]

    async def read_lamp_data(self, slave_id: int) -> LampData:
        state = self._get_state(slave_id)

        if state.status == LampStatusCode.BURNED_OUT:
            return LampData(
                status=state.status,
                is_on=False,
                hours_active=state.hours_active,
                junction_temp_avg=state.junction_temp_avg,
                voltage_spike_count=state.voltage_spike_count,
                on_off_cycles=state.on_off_cycles,
                humidity_avg=state.humidity_avg,
                voltage=0.0,
                current_ma=0.0,
                ambient_temp=state.ambient_temp + random.uniform(-0.5, 0.5),
                reflector_position=state.reflector_position,
            )

        # Инкремент наработки (каждый цикл ~5 сек ≈ 0.0014 ч, ускоряем для демо)
        if state.is_on:
            state.hours_active += 1

        # Шанс перегореть: ОТКЛЮЧЕН (по требованию пользователя, лампы не ломаются сами)
        # if state.is_on and random.random() < 0.03:
        #    state.status = LampStatusCode.BURNED_OUT
        #    return LampData(...)

        # Плавающие показатели
        state.junction_temp_avg += random.uniform(-0.5, 0.5)
        state.junction_temp_avg = max(20.0, min(90.0, state.junction_temp_avg))

        state.humidity_avg += random.uniform(-1.0, 1.0)
        state.humidity_avg = max(30.0, min(95.0, state.humidity_avg))

        state.ambient_temp += random.uniform(-0.3, 0.3)
        state.ambient_temp = max(-30.0, min(45.0, state.ambient_temp))

        voltage = random.uniform(218.0, 232.0)
        current_ma = random.uniform(300.0, 400.0) if state.is_on else 0.0

        # Редкие скачки напряжения
        if random.random() < 0.05:
            state.voltage_spike_count += 1

        return LampData(
            status=state.status,
            is_on=state.is_on,
            hours_active=state.hours_active,
            junction_temp_avg=round(state.junction_temp_avg, 1),
            voltage_spike_count=state.voltage_spike_count,
            on_off_cycles=state.on_off_cycles,
            humidity_avg=round(state.humidity_avg, 1),
            voltage=round(voltage, 1),
            current_ma=round(current_ma, 1),
            ambient_temp=round(state.ambient_temp, 1),
            reflector_position=state.reflector_position,
        )

    async def write_lamp_on(self, slave_id: int, on: bool) -> None:
        state = self._get_state(slave_id)
        if state.status == LampStatusCode.BURNED_OUT:
            return  # перегоревшую лампу нельзя включить
        state.is_on = on
        state.on_off_cycles += 1

    async def write_reflector(self, slave_id: int, open: bool) -> None:
        state = self._get_state(slave_id)
        state.reflector_position = 180 if open else 0

    async def set_status(self, slave_id: int, status: LampStatusCode) -> None:
        state = self._get_state(slave_id)
        state.status = status
        if status == LampStatusCode.BURNED_OUT:
            state.is_on = False
