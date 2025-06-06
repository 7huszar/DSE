from __future__ import annotations

import math
from random import uniform
from collections import defaultdict
from typing import Dict, Tuple, List

import numpy as np
from geographiclib.geodesic import Geodesic

from vehicle import Vehicle

# ------------------------------------------------------------------
# CONSTANTS & VINs --------------------------------------------------
# ------------------------------------------------------------------
FAST_VIN: str = "4A3AK24FX6E028812"
SLOW_VIN: str = "1N6SD16S8NC343640"

WAYPOINTS: List[Tuple[float, float]] = [
    (48.230472, 16.386757),  # A – end of first street
    (48.230551, 16.386916),  # B – turn to street back
    (48.236999, 16.379617),  # C – end of street back
    (48.236899, 16.379481),  # D – starting point
]

STOP_POINT: Tuple[float, float] = (48.231614, 16.385300)
STOP_THRESHOLD: float = 15.0  # metres

_idx_by_vin: Dict[str, int] = defaultdict(int)
_last_pos: Dict[str, Tuple[float, float]] = {}
_slow_parked: bool = False

def _bearing_and_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
    """Return (bearing°, distance m) on WGS‑84 from *p1* to *p2*."""
    inv = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
    return inv["azi1"], inv["s12"]

def mess_with_vehicle(vehicle: Vehicle) -> None:
    """Set *vehicle* direction + acceleration each tick so it follows the
    scenario rules described above."""
    global _slow_parked

    if vehicle.vin == SLOW_VIN and _slow_parked:
        return

    if vehicle.vin == SLOW_VIN and not _slow_parked:
        _, dist_to_stop = _bearing_and_distance(
            vehicle.latitude, vehicle.longitude, *STOP_POINT
        )
        if dist_to_stop <= STOP_THRESHOLD:
            # Snap onto the stop‑point and park permanently
            vehicle.latitude, vehicle.longitude = STOP_POINT
            vehicle.velocity = 0.0
            vehicle.acceleration = 0.0
            _slow_parked = True
            return


    # Keep a history of last positions for inter‑vehicle distance
    _last_pos[vehicle.vin] = (vehicle.latitude, vehicle.longitude)

    idx = _idx_by_vin[vehicle.vin]
    tgt_lat, tgt_lon = WAYPOINTS[idx]

    bearing_deg, remaining_m = _bearing_and_distance(
        vehicle.latitude, vehicle.longitude, tgt_lat, tgt_lon
    )

    # Set unit direction vector (east, north) so Vehicle.sample() walks geodesic.
    rad = math.radians(bearing_deg)
    vehicle.direction = np.array([math.sin(rad), math.cos(rad)], dtype=float)


def compute_dst_front(vehicle: Vehicle) -> float:
    if vehicle.vin == FAST_VIN and SLOW_VIN in _last_pos:
        _, dist = _bearing_and_distance(
            vehicle.latitude,
            vehicle.longitude,
            *_last_pos[SLOW_VIN],
        )
        return dist
    elif vehicle.vin == FAST_VIN:
        return 50.0

    if vehicle.vin == SLOW_VIN:
        return uniform(10.0, 20.0)

    return 0.0
