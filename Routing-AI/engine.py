import math
import random
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

@dataclass
class DroneConfig:
    base_mass: float = 3.0
    lamp_mass: float = 0.1  # Significantly reduced to realistic payload (e.g. light bulbs)
    energy_rate: float = 4.0
    wind_k: float = 0.3
    avg_speed_mps: float = 10.0
    battery_capacity_wh: float = 500.0 # Increased for industrial drone
    watts_per_unit: float = 10.0
    avg_power_watts: float = 400.0

class DronePhysicsEngine:
    def __init__(self, wind_speed: float, wind_deg: float, config: DroneConfig = DroneConfig()):
        self.wind_speed = wind_speed
        self.wind_deg = wind_deg
        self.config = config

    def _get_wind_vector(self) -> Tuple[float, float]:
        """
        Возвращает вектор КУДА дует ветер.
        Meteo 90 (Восточный) -> Дует на Запад (вектор -X).
        """
        rad = math.radians(90 - self.wind_deg)
        ux = math.cos(rad)
        uy = math.sin(rad)
        
        # Инвертируем, так как нас интересует поток воздуха (КУДА дует)
        wx = self.wind_speed * (-ux)
        wy = self.wind_speed * (-uy)
        
        return wx, wy

    def calculate_leg_cost(self, p1_xy: Tuple[float, float], p2_xy: Tuple[float, float], current_payload_count: int) -> float:
        dx = p2_xy[0] - p1_xy[0]
        dy = p2_xy[1] - p1_xy[1]
        dist = math.sqrt(dx**2 + dy**2)
        
        if dist == 0: return 0.0

        total_mass = self.config.base_mass + (current_payload_count * self.config.lamp_mass)
        mass_factor = total_mass / self.config.base_mass

        wx, wy = self._get_wind_vector()
        norm_dx, norm_dy = dx/dist, dy/dist
        wind_proj = (norm_dx * wx) + (norm_dy * wy)
        
        wind_factor = 1.0 - (self.config.wind_k * wind_proj)
        wind_factor = np.clip(wind_factor, 0.5, 2.0)

        return self.config.energy_rate * dist * mass_factor * wind_factor
    
    def energy_to_time_minutes(self, total_energy: float) -> float:
        """Примерная конвертация энергии в время"""
        total_joules = total_energy * self.config.watts_per_unit
        time_seconds = total_joules / self.config.avg_power_watts
        return time_seconds / 60.0

    def energy_to_battery_percent(self, total_energy: float) -> float:
        """Конвертация в % батареи"""
        used_wh = (total_energy * self.config.watts_per_unit) / 3600.0
        return (used_wh / self.config.battery_capacity_wh) * 100.0

class GeneticOptimizer:
    def __init__(self, physics_engine: DronePhysicsEngine, depot_xy: Tuple[float, float] = (0, 0)):
        self.physics = physics_engine
        self.depot = depot_xy

    def _calculate_route_energy(self, route_nodes_xy: List[Dict]) -> float:
        total_energy = 0.0
        current_pos = self.depot
        load = len(route_nodes_xy)

        for node in route_nodes_xy:
            pos = node['pos_xy']
            total_energy += self.physics.calculate_leg_cost(current_pos, pos, load)
            current_pos = pos
            load -= 1

        total_energy += self.physics.calculate_leg_cost(current_pos, self.depot, 0)
        return total_energy

    def solve_nearest_neighbor(self, lamps_xy_list: List[Dict]) -> Tuple[List[Dict], float]:
        """Алгоритм: Всегда лети к ближайшей точке (игнорирует ветер и массу)."""
        if not lamps_xy_list: return [], 0.0
        
        route = []
        remaining = lamps_xy_list.copy()
        current_pos = self.depot
        
        while remaining:
            nearest = min(remaining, key=lambda l: math.dist(current_pos, l['pos_xy']))
            route.append(nearest)
            current_pos = nearest['pos_xy']
            remaining.remove(nearest)
            
        energy = self._calculate_route_energy(route)
        return route, energy

    def solve(self, lamps_xy_list: List[Dict], pop_size: int = 50, generations: int = 80) -> Tuple[List[Dict], float]:
        if not lamps_xy_list: return [], 0.0
        if len(lamps_xy_list) == 1: 
            return lamps_xy_list, self._calculate_route_energy(lamps_xy_list)

        # Ensure population size is not larger than factorial of len(lamps) for very small sets
        # But for simplicity, we just sample.
        
        population = [random.sample(lamps_xy_list, len(lamps_xy_list)) for _ in range(pop_size)]
        
        best_route = population[0]
        best_score = float('inf')

        for gen in range(generations):
            scored = [(ind, self._calculate_route_energy(ind)) for ind in population]
            scored.sort(key=lambda x: x[1])
            
            if scored[0][1] < best_score:
                best_score = scored[0][1]
                best_route = scored[0][0]

            # Elitism: keep top 20%
            elite_count = int(pop_size * 0.2)
            survivors = [ind for ind, s in scored[:elite_count]]
            
            new_pop = survivors[:]
            
            while len(new_pop) < pop_size:
                # Tournament selection could be better, but random from elite is okay for now
                if len(survivors) >= 2:
                    p1, p2 = random.sample(survivors, 2)
                else:
                    p1 = survivors[0]
                    p2 = random.sample(population, 1)[0] # Fallback
                
                child = self._crossover(p1, p2)
                self._mutate(child)
                new_pop.append(child)
            
            population = new_pop

        return best_route, best_score

    def _crossover(self, p1: List[Dict], p2: List[Dict]) -> List[Dict]:
        """Order Crossover (OX1) logic"""
        size = len(p1)
        a, b = sorted(random.sample(range(size), 2))
        child = [None] * size
        
        # Copy segment from p1
        child[a:b] = p1[a:b]
        
        # Fill remaining from p2
        # Use IDs to identify uniqueness efficiently
        child_ids = set(node['id'] for node in child[a:b])
        p2_rem = [item for item in p2 if item['id'] not in child_ids]
        
        idx = 0
        for i in range(size):
            if child[i] is None:
                child[i] = p2_rem[idx]
                idx += 1
        return child

    def _mutate(self, individual: List[Dict]) -> None:
        """Swap mutation"""
        if random.random() < 0.2:
            i1, i2 = random.sample(range(len(individual)), 2)
            individual[i1], individual[i2] = individual[i2], individual[i1]
