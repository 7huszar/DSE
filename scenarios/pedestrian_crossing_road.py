from vehicle import Vehicle
import numpy as np
import math
from geographiclib.geodesic import Geodesic

# (latitude, longitude)
WAYPOINTS: list[tuple[float, float]] = [
    (48.230472, 16.386757),  # A - end of first street
    (48.230551, 16.386916),  # B - turn to street back
    (48.236999, 16.379617),  # C - end of street back
    (48.236899, 16.379481),  # D - starting point
]

_TARGET_SPEED = 15.0  # m/s  ≈ 54 km/h
_ACCEL        = 2.0   # m/s²
_BRAKE        = -5.0  # m/s²
_EPSILON      = 1.0   # metres – considered "arrived"

_PED_LON = 16.380417
_PED_LAT = 48.236084

_current_idx: int = 0  # index of the active goal in WAYPOINTS

def _bearing_and_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Return (bearing°, distance m) on WGS‑84 from point 1 to point 2."""
    inv = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
    return inv["azi1"], inv["s12"]



def compute_dst_front(vehicle: Vehicle) -> float:
    return _bearing_and_distance(vehicle.latitude, vehicle.longitude, _PED_LAT, _PED_LON)[1]

def mess_with_vehicle(vehicle: Vehicle) -> None:
    global _current_idx

    tgt_lat, tgt_lon = WAYPOINTS[_current_idx]

    bearing_deg, remaining_m = _bearing_and_distance(
        vehicle.latitude, vehicle.longitude, tgt_lat, tgt_lon
    )

    rad = math.radians(bearing_deg)
    vehicle.direction = np.array([math.sin(rad), math.cos(rad)], dtype=float)

    if remaining_m < _EPSILON:

        vehicle.latitude = tgt_lat
        vehicle.longitude = tgt_lon
        _current_idx = (_current_idx + 1) % len(WAYPOINTS)
        vehicle.velocity = 0.0
        vehicle.acceleration = 0.0

        return

    stopping_dist = (vehicle.velocity ** 2) / (2 * -_BRAKE) if vehicle.velocity > 0 else 0

    if remaining_m <= stopping_dist + 2.0:  # extra buffer
        vehicle.acceleration = _BRAKE
    elif vehicle.velocity < _TARGET_SPEED:
        vehicle.acceleration = _ACCEL
    else:
        vehicle.acceleration = 0.0
