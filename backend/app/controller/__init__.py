from app.core.config import settings
from app.controller.base import BaseController


def get_controller() -> BaseController:
    if settings.CONTROLLER_MODE == "modbus":
        from app.controller.modbus import ModbusController
        return ModbusController(
            port=settings.RS485_PORT,
            baudrate=settings.RS485_BAUDRATE,
        )
    from app.controller.mock import MockController
    return MockController()
