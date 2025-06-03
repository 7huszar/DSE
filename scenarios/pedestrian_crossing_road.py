from vehicle import Vehicle
import numpy as np
from haversine import haversine, Unit

def compute_dst_front(vehicle: Vehicle) -> float:

    # x = longitude
    # y = latitude

    dir = vehicle.direction

    ped = np.array([48.235270, 16.381342])
    v = np.array([vehicle.longitude, vehicle.latitude])

    to_ped = ped - v

    dot_prod = np.dot(dir, to_ped)

    if dot_prod < 0:
        return haversine(ped, v, unit=Unit.METERS)
    else:
        return np.random.uniform(50, 60)
