# -----------------------------------------------------------------------------
# vehicle.py  – updated `sample` method that uses WGS‑84 geodesics instead of
# planar dx/dy so the car moves accurately towards whatever bearing its
# `direction` indicates.
# -----------------------------------------------------------------------------
import math
import time
import numpy as np
from geographiclib.geodesic import Geodesic


class Vehicle:
    def __init__(
            self,
            vin: str,
            longitude: float,
            latitude: float,
            velocity: float = 0.0,
            acceleration: float = 0.0,
            direction: np.ndarray = np.array([1.0, 0.0], dtype=float),
            dst_front: float = 10,
            dst_back: float = 10,
    ) -> None:
        self.longitude = longitude
        self.latitude = latitude
        self.velocity = velocity
        self.acceleration = acceleration
        self.direction = direction.astype(float)
        self.internal_time = time.time()
        self.vin = vin
        self.dst_front = dst_front
        self.dst_back = dst_back

    def sample(self, acceleration: float = None, direction: np.ndarray = None) -> dict[str, float]:

        delta_time = time.time() - self.internal_time
        self.internal_time += delta_time

        if acceleration is not None:
            self.acceleration = acceleration
        if direction is not None:
            self.direction = direction.astype(float)

        # f(t) = t * acc + vel
        # F(t) = 0.5(t^2) * acc + vel * t + C
        distance = (self.acceleration * (delta_time ** 2) / 2.0) + (self.velocity * delta_time)

        self.velocity += self.acceleration * delta_time

        if distance < 0.0:
            distance = 0.0
        if self.velocity <= 0.0:
            self.velocity = 0.0
            if self.acceleration < 0.0:
                self.acceleration = 0.0

        if distance > 0.0:
            norm = np.linalg.norm(self.direction)
            if norm == 0:
                raise ValueError("Direction vector must be non‑zero.")
            unit_dir = self.direction / norm

            # Bearing in degrees where 0° = north, 90° = east (mathematical
            # azimuth is measured clockwise from north)
            bearing_deg = math.degrees(math.atan2(unit_dir[0], unit_dir[1]))

            geo = Geodesic.WGS84.Direct(self.latitude, self.longitude, bearing_deg, distance)
            self.latitude = geo["lat2"]
            self.longitude = geo["lon2"]

        return {"lat": self.latitude, "long": self.longitude, "internal_time": self.internal_time}

    # ------------------------------------------------------------------
    def __str__(self) -> str:
        return (
            f"Vehicle("
            f"longitude={self.longitude}, "
            f"latitude={self.latitude}, "
            f"velocity={self.velocity}, "
            f"acceleration={self.acceleration}, "
            f"direction={self.direction}, "
            f"internal_time={self.internal_time}, "
            f"vin={self.vin}, "
            f"distance_front={self.dst_front}, "
            f"distance_back={self.dst_back}"
            f")"
        )

