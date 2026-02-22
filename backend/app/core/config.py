import os


class Settings:
    CONTROLLER_MODE: str = os.getenv("CONTROLLER_MODE", "mock")  # mock | modbus
    RS485_PORT: str = os.getenv("RS485_PORT", "/dev/ttyUSB0")
    RS485_BAUDRATE: int = int(os.getenv("RS485_BAUDRATE", "9600"))
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "5"))  # секунды
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///lamps_30.db")
    AI_SERVICE_URL: str = os.getenv("AI_SERVICE_URL", "http://localhost:8001")
    LAMP_COUNT: int = int(os.getenv("LAMP_COUNT", "30"))
    # Координаты города для расчёта рассвета/заката (КАИ, Казань)
    CITY_LAT: float = float(os.getenv("CITY_LAT", "55.752"))
    CITY_LNG: float = float(os.getenv("CITY_LNG", "48.745"))

    # API Keys
    YANDEX_WEATHER_API_KEY: str | None = os.getenv("YANDEX_WEATHER_API_KEY")

    def __init__(self):
        # Load from .env file if available and not set in env
        if not self.YANDEX_WEATHER_API_KEY:
            try:
                from dotenv import load_dotenv
                load_dotenv(override=True)
                self.YANDEX_WEATHER_API_KEY = os.getenv("YANDEX_WEATHER_API_KEY")
            except ImportError:
                pass

settings = Settings()
