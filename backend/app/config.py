import os


class Settings:
    CONTROLLER_MODE: str = os.getenv("CONTROLLER_MODE", "mock")  # mock | modbus
    RS485_PORT: str = os.getenv("RS485_PORT", "/dev/ttyUSB0")
    RS485_BAUDRATE: int = int(os.getenv("RS485_BAUDRATE", "9600"))
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "5"))  # секунды
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///lamps.db")


settings = Settings()
