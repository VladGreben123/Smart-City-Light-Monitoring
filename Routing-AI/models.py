from pydantic import BaseModel
from typing import List

class LampInput(BaseModel):
    id: str
    lat: float
    lng: float

class OptimizeRequest(BaseModel):
    lamps: List[LampInput]
    depot_lat: float
    depot_lng: float
    wind_speed: float = None 
    wind_deg: float = None   

class OptimizeResponse(BaseModel):
    route_ids: List[str]
    route_geometry: List[List[float]]
    
    # Энергия
    total_energy: float            
    naive_energy: float            
    savings_percent: float        
    
    # НОВОЕ: Бизнес-метрики
    flight_time_minutes: float     # Расчетное время полета
    battery_usage_percent: float   # Сколько % батареи будет потрачено
    
    # Погода
    wind_speed: float              
    wind_deg: float
    
    # НОВОЕ: Информация о сравнении
    baseline_algorithm: str        # С чем сравнивали (напр. "Nearest Neighbor")