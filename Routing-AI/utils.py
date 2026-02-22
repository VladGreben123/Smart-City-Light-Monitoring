import math
from typing import Tuple

def geo_to_meters(lat: float, lng: float, center_lat: float, center_lng: float) -> Tuple[float, float]:
    """
    Конвертирует географические координаты (lat, lng) в метры (x, y) относительно центра.
    Использует простую проекцию для малых расстояний.
    1 градус широты ~ 111200 метров.
    1 градус долготы ~ 111200 * cos(lat) метров.
    """
    y = (lat - center_lat) * 111200
    x = (lng - center_lng) * 111200 * math.cos(math.radians(center_lat))
    return x, y
