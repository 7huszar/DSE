import math

import time

import numpy as np

class Vehicle:
    def __init__(self, vin: str, longitude: float, latitude: float, velocity: float = 0.0, acceleration: float =0.0, direction=np.array([1.0, 0.0], dtype=float), dst_front: float = 10, dst_back: float = 10) -> None:
        self.longitude: float = longitude
        self.latitude: float = latitude
        self.velocity: float = velocity
        self.acceleration: float = acceleration
        self.direction = direction
        self.internal_time: float = time.time()
        self.vin: str = vin
        self.dst_front: float = dst_front
        self.dst_back: float = dst_back

    earth_radius: float = 6371000.0

    def sample(self, acceleration: float = None, direction=None) -> dict[str, float]:
        delta_time = time.time() - self.internal_time
        self.internal_time+= delta_time
        if acceleration is not None:
            self.acceleration = acceleration
        if direction is not None:
            self.direction = direction

        # f(t) = t * acc + vel
        # F(t) = 0.5(t^2) * acc + vel * t + C

        distance = self.acceleration * (math.pow(delta_time, 2.0) / 2.0) + (self.velocity * delta_time)

        # x = longitude
        # y = latitude
        dx = self.direction[0] * distance
        dy = self.direction[1] * distance

        self.latitude += (dy / self.earth_radius) * (180 / math.pi)
        self.longitude += (dx / (self.earth_radius * math.cos(math.radians(self.latitude)))) * (180 / math.pi)

        return {
            "lat": self.latitude,
            "long": self.longitude,
            "internal_time": self.internal_time
        }

    def __str__(self) -> str:
        return (f"Vehicle(longitude: "
                f"{self.longitude}, "
                f"latitude: {self.latitude}, "
                f"velocity: {self.velocity}, "
                f"acceleration: {self.acceleration}, "
                f"direction: {self.direction}, "
                f"internal_time: {self.internal_time}, "
                f"vin: {self.vin}, "
                f"distance_front: {self.dst_front}, "
                f"distance_back: {self.dst_back})")
