"""
Контроллер Modbus RTU через RS485.

Используется при CONTROLLER_MODE=modbus и наличии реального оборудования.
Карта регистров:

Input Registers (read-only, FC=04):
  Адрес | Поле                | Множитель
  ------+---------------------+----------
  0     | status (0/1/2)      | —
  1     | hours_active         | —
  2     | junction_temp_avg    | ÷10
  3     | voltage_spike_count  | —
  4     | on_off_cycles        | —
  5     | humidity_avg         | ÷10
  6     | voltage              | ÷10
  7     | current_ma           | —
  8     | ambient_temp         | ÷10  (знаковое)
  9     | reflector_position   | —

Holding Registers (write, FC=06):
  Адрес | Поле
  ------+------------------
  0     | lamp on/off (0/1)
  1     | reflector (0/1)
"""

import asyncio
import struct

from app.controller.base import BaseController, LampData, LampStatusCode


class ModbusController(BaseController):
    """Реальный Modbus RTU клиент через pymodbus."""

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600) -> None:
        self._port = port
        self._baudrate = baudrate
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        try:
            from pymodbus.client import ModbusSerialClient
            self._client = ModbusSerialClient(
                port=self._port,
                baudrate=self._baudrate,
                parity="N",
                stopbits=1,
                bytesize=8,
                timeout=1,
            )
            self._client.connect()
        except ImportError:
            raise RuntimeError(
                "pymodbus не установлен. Установите: pip install pymodbus"
            )

    async def read_lamp_data(self, slave_id: int) -> LampData:
        self._ensure_client()
        result = await asyncio.to_thread(
            self._client.read_input_registers,
            address=0,
            count=10,
            slave=slave_id,
        )
        if result.isError():
            raise ConnectionError(
                f"Modbus read error slave_id={slave_id}: {result}"
            )
        regs = result.registers

        # Регистр 8 (ambient_temp) может быть отрицательным — signed int16
        raw_ambient = regs[8]
        ambient_signed = struct.unpack("h", struct.pack("H", raw_ambient))[0]

        return LampData(
            status=LampStatusCode(regs[0]),
            is_on=regs[0] == LampStatusCode.OK,
            hours_active=regs[1],
            junction_temp_avg=regs[2] / 10.0,
            voltage_spike_count=regs[3],
            on_off_cycles=regs[4],
            humidity_avg=regs[5] / 10.0,
            voltage=regs[6] / 10.0,
            current_ma=regs[7],
            ambient_temp=ambient_signed / 10.0,
            reflector_position=regs[9],
        )

    async def write_lamp_on(self, slave_id: int, on: bool) -> None:
        self._ensure_client()
        await asyncio.to_thread(
            self._client.write_register,
            address=0,
            value=1 if on else 0,
            slave=slave_id,
        )

    async def write_reflector(self, slave_id: int, open: bool) -> None:
        self._ensure_client()
        await asyncio.to_thread(
            self._client.write_register,
            address=1,
            value=1 if open else 0,
            slave=slave_id,
        )
