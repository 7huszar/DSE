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

def set_all_vehicles(vehicles_input):
    global vehicles
    vehicles = vehicles_input


FAST_VIN: str = "4A3AK24FX6E028812"
SLOW_VIN: str = "1N6SD16S8NC343640"

# Default speeds and acceleration
_DEFAULT_TARGET_SPEED = 15.0  # m/s  ≈ 54 km/h
_CROSSING_TARGET_SPEED = 25.0  # m/s for crossing segments (~90 km/h)
_ACCEL        = 2.0   # m/s²
_BRAKE        = -5.0  # m/s²
_EPSILON      = 1.0   # metres – considered "arrived"

# Indices of WAYPOINTS where cars should speed up (A->B and C->D)
_CROSSING_SEGMENTS = {0, 2}


def _bearing_and_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Return (bearing°, distance m) on WGS‑84 from point 1 to point 2."""
    inv = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
    return inv["azi1"], inv["s12"]


def compute_dst_front(vehicle: Vehicle) -> float:
    global vehicles
    if vehicle.vin == FAST_VIN:
        slow_vehicle = vehicles[SLOW_VIN]
        _, dist = _bearing_and_distance(
            vehicle.latitude,
            vehicle.longitude,
            slow_vehicle.latitude,
            slow_vehicle.longitude
        )
        return dist

    return uniform(10.0, 20.0)


def compute_dst_back(vehicle: Vehicle) -> float:
    global vehicles
    if vehicle.vin == SLOW_VIN:
        return compute_dst_front(vehicles[FAST_VIN])

    return uniform(15.0, 20.0)


def mess_with_vehicle(vehicle: Vehicle) -> None:
    # Ensure each vehicle tracks its own waypoint index
    if not hasattr(vehicle, 'current_idx'):
        vehicle.current_idx = 0

    # Determine target waypoint for this vehicle
    tgt_lat, tgt_lon = WAYPOINTS[vehicle.current_idx]

    bearing_deg, remaining_m = _bearing_and_distance(
        vehicle.latitude, vehicle.longitude, tgt_lat, tgt_lon
    )

    # Update direction vector toward target
    rad = math.radians(bearing_deg)
    vehicle.direction = np.array([math.sin(rad), math.cos(rad)], dtype=float)

    # If arrived at waypoint, snap position, reset motion, and advance index
    if remaining_m < _EPSILON:
        vehicle.latitude = tgt_lat
        vehicle.longitude = tgt_lon
        vehicle.current_idx = (vehicle.current_idx + 1) % len(WAYPOINTS)
        vehicle.velocity = 0.0
        vehicle.acceleration = 0.0
        return

    # Choose target speed based on segment
    target_speed = _CROSSING_TARGET_SPEED if vehicle.current_idx in _CROSSING_SEGMENTS else _DEFAULT_TARGET_SPEED

    # Compute stopping distance
    stopping_dist = (vehicle.velocity ** 2) / (2 * -_BRAKE) if vehicle.velocity > 0 else 0

    # Decide whether to brake, accelerate, or coast
    if remaining_m <= stopping_dist + 2.0:
        # Always able to brake if too close
        vehicle.acceleration = _BRAKE
    elif vehicle.velocity < target_speed:
        # Accelerate towards the segment's target speed
        vehicle.acceleration = _ACCEL
    else:
        # Coast at or above the segment's target speed
        vehicle.acceleration = 0.0
