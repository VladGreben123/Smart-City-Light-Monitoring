"""Модуль управления оверрайдом погоды (Debug)."""

# Override для тестирования
_override_enabled: bool = False
_override_is_bad: bool = False

def set_weather_override(enabled: bool, is_bad: bool = False) -> None:
    global _override_enabled, _override_is_bad
    _override_enabled = enabled
    _override_is_bad = is_bad

def get_weather_override() -> dict:
    return {"enabled": _override_enabled, "is_bad": _override_is_bad}
