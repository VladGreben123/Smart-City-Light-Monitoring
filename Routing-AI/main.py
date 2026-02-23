from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import OptimizeRequest, OptimizeResponse
from engine import DronePhysicsEngine, GeneticOptimizer
from weather_service import default_weather_service
from utils import geo_to_meters
import math

app = FastAPI(title="Smart Drone Routing Core")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/api/v1/optimize", response_model=OptimizeResponse)
async def optimize_endpoint(req: OptimizeRequest):
    if not req.lamps:
        raise HTTPException(status_code=400, detail="Lamps list is empty")

    # 1. Погода
    if req.wind_speed is not None and req.wind_deg is not None:
        wind_speed, wind_deg = req.wind_speed, req.wind_deg
    else:
        wind_speed, wind_deg = await default_weather_service.get_wind_data(req.depot_lat, req.depot_lng)

    # 2. Инициализация
    physics = DronePhysicsEngine(wind_speed, wind_deg)
    optimizer = GeneticOptimizer(physics, depot_xy=(0, 0)) # depot is (0,0) in local coords

    # 3. Конвертация
    lamp_map = {lamp.id: lamp for lamp in req.lamps}
    lamps_xy = []
    for lamp in req.lamps:
        x, y = geo_to_meters(lamp.lat, lamp.lng, req.depot_lat, req.depot_lng)
        lamps_xy.append({'id': lamp.id, 'pos_xy': (x, y)})

    # 4. Быстрая оптимизация (Nearest Neighbor)
    best_route, best_energy = optimizer.solve_nearest_neighbor(lamps_xy)
    naive_route, naive_energy = best_route, best_energy

    # 6. Геометрия
    geometry = [[req.depot_lat, req.depot_lng]]
    for node in best_route:
        lamp_data = lamp_map[node['id']]
        geometry.append([lamp_data.lat, lamp_data.lng])
    geometry.append([req.depot_lat, req.depot_lng])

    # 7. Метрики
    savings = 0.0
    if naive_energy > 0:
        savings = ((naive_energy - best_energy) / naive_energy) * 100
    
    # Новые метрики
    flight_time = physics.energy_to_time_minutes(best_energy)
    battery_usage = physics.energy_to_battery_percent(best_energy)

    return OptimizeResponse(
        route_ids=[node['id'] for node in best_route],
        route_geometry=geometry,
        total_energy=round(best_energy, 2),
        naive_energy=round(naive_energy, 2),
        savings_percent=round(savings, 2),
        flight_time_minutes=round(flight_time, 1),
        battery_usage_percent=round(battery_usage, 1),
        wind_speed=round(wind_speed, 1),
        wind_deg=round(wind_deg, 1),
        baseline_algorithm="Nearest Neighbor (Distance)"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
