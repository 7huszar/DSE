import math

import time

class Vehicle:
    def __init__(self, vin, longitude, latitude, velocity=0.0, acceleration=0.0, direction=[1.0, 0.0], dst_front=10, dst_back=10):
        self.longitude = longitude
        self.latitude = latitude
        self.velocity = velocity
        self.acceleration = acceleration
        self.direction = direction
        self.internal_time = time.time()
        self.vin = vin
        self.dst_front = dst_front
        self.dst_back = dst_back

    earth_radius = 6371000

    def sample(self, acceleration, direction):
        delta_time = time.time() - self.internal_time
        self.internal_time += delta_time
        self.acceleration = acceleration
        self.direction = direction

        # f(t) = t * acc + vel
        # F(t) = 0.5(t^2) * acc + vel * t + C

        distance = self.acceleration * (math.pow(delta_time, 2) / 2) + (self.velocity * delta_time)

        dx = self.direction[0] * distance
        dy = self.direction[1] * distance

        self.latitude += (dy / self.earth_radius) * (180 / math.pi)
        self.longitude += (dx / (self.earth_radius * math.cos(math.radians(self.latitude)))) * (180 / math.pi)

        return [self.latitude, self.longitude, self.internal_time]

    def __str__(self):
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
