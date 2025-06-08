from numpy.random import uniform
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

vehicles = {}

FAST_VIN: str = "4A3AK24FX6E028812"
SLOW_VIN: str = "1N6SD16S8NC343640"

_DEFAULT_TARGET_SPEED = 15.0  # m/s (≈54 km/h)
_CROSSING_TARGET_SPEED = 25.0  # m/s (≈90 km/h) for crossing segments
_ACCEL = 2.0   # m/s²
_BRAKE = -5.0  # m/s²
_EPSILON = 1.0  # metres – considered "arrived"
# Segments where to use the higher crossing speed (A->B, C->D)
_CROSSING_SEGMENTS = {0, 2}



def set_all_vehicles(vehicles_input):
    global vehicles
    vehicles = vehicles_input
    del vehicles[SLOW_VIN]


def _bearing_and_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Return (bearing°, distance m) on WGS-84 from point 1 to point 2."""
    inv = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
    return inv["azi1"], inv["s12"]


def mess_with_vehicle(vehicle: Vehicle) -> None:
    # Only process the fast vehicle
    if vehicle.vin != FAST_VIN:
        return

    # Initialize waypoint index if needed
    if not hasattr(vehicle, 'current_idx'):
        vehicle.current_idx = 0

    # Target waypoint
    tgt_lat, tgt_lon = WAYPOINTS[vehicle.current_idx]
    bearing_deg, remaining_m = _bearing_and_distance(
        vehicle.latitude, vehicle.longitude, tgt_lat, tgt_lon
    )

    # Update direction vector
    rad = math.radians(bearing_deg)
    vehicle.direction = np.array([math.sin(rad), math.cos(rad)], dtype=float)

    # If arrived: snap to waypoint and advance
    if remaining_m < _EPSILON:
        vehicle.latitude, vehicle.longitude = tgt_lat, tgt_lon
        vehicle.current_idx = (vehicle.current_idx + 1) % len(WAYPOINTS)
        vehicle.velocity = 0.0
        vehicle.acceleration = 0.0
        return

    # Choose speed based on segment
    target_speed = (_CROSSING_TARGET_SPEED if vehicle.current_idx in _CROSSING_SEGMENTS
                    else _DEFAULT_TARGET_SPEED)

    # Stopping distance
    stopping_dist = (vehicle.velocity ** 2) / (2 * -_BRAKE) if vehicle.velocity > 0 else 0

    # Decide motion
    if remaining_m <= stopping_dist + 2.0:
        vehicle.acceleration = _BRAKE
    elif vehicle.velocity < target_speed:
        vehicle.acceleration = _ACCEL
    else:
        vehicle.acceleration = 0.0
