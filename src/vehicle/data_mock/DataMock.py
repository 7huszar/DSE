import json
import os
import time
import logging
from vehicle import Vehicle
import requests
import random
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

with open("vehicles.json", "r") as f:
    vehicle_config = json.load(f)

### CONSTANTS START ###

BASE_URI = "http://location-sender-{}/data"

MAX_DISTANCE_FRONT = float(os.environ.get("MAX_DST_FRONT", 50))
MIN_DISTANCE_FRONT = float(os.environ.get("MIN_DST_FRONT", 0.5))

MAX_DISTANCE_BACK = float(os.environ.get("MAX_DST_BACK", 50))
MIN_DISTANCE_BACK = float(os.environ.get("MIN_DST_BACK", 0.5))

MAX_CHANGE_RATE_PERCENT = float(os.environ.get("MAX_CHANGE_RATE", 0.15))

# Vehicle-specific last distances (using VIN as key)
last_distances = {}

### CONSTANTS END ###

vehicles = []
for vehicle_data in vehicle_config:
    v = Vehicle(
        vehicle_data["vin"],
        velocity=vehicle_data["vel"],
        longitude=vehicle_data["lon"],
        latitude=vehicle_data["lat"],
        direction=vehicle_data["dir"]
    )
    vehicles.append(v)
    # Initialize last distances for each vehicle
    last_distances[v.vin] = {
        'front': float(os.environ.get("LAST_DST_FRONT", 0)),
        'back': float(os.environ.get("LAST_DST_BACK", 0))
    }

def update_car(vehicle):
    """Update vehicle position and send data"""
    vin = vehicle.vin
    last_front = last_distances[vin]['front']
    last_back = last_distances[vin]['back']

    # Get new position
    new_coord = vehicle.sample(0, 0)

    # Calculate front distance
    if last_front == 0:
        distance_front = random.choice(np.arange(MIN_DISTANCE_FRONT, MAX_DISTANCE_FRONT, 0.1))
    else:
        distance_front = 0
        while distance_front < MIN_DISTANCE_FRONT or distance_front > MAX_DISTANCE_FRONT:
            min_range = max(MIN_DISTANCE_FRONT, (1-MAX_CHANGE_RATE_PERCENT)*last_front)
            max_range = min(MAX_DISTANCE_FRONT, (1+MAX_CHANGE_RATE_PERCENT)*last_front)
            distance_front = random.choice(np.arange(min_range, max_range, 0.1))

    # Calculate back distance
    if last_back == 0:
        distance_back = random.choice(np.arange(MIN_DISTANCE_BACK, MAX_DISTANCE_BACK, 0.1))
    else:
        distance_back = 0
        while distance_back < MIN_DISTANCE_BACK or distance_back > MAX_DISTANCE_BACK:
            min_range = max(MIN_DISTANCE_BACK, (1-MAX_CHANGE_RATE_PERCENT)*last_back)
            max_range = min(MAX_DISTANCE_BACK, (1+MAX_CHANGE_RATE_PERCENT)*last_back)
            distance_back = random.choice(np.arange(min_range, max_range, 0.1))

    # Update last distances
    last_distances[vin]['front'] = distance_front
    last_distances[vin]['back'] = distance_back

    logger.info(f"Vehicle {vin}: Distance front: {distance_front:.1f}m, back: {distance_back:.1f}m, speed: {vehicle.velocity*3.6:.1f} km/h")

    # Prepare data with speed
    data = {
        "vin": vehicle.vin,
        "lat": new_coord[0],
        "long": new_coord[1],
        "time": new_coord[2],
        "distance_front": distance_front,
        "distance_back": distance_back,
        "speed": vehicle.velocity * 3.6  # Convert m/s to km/h
    }

    # Send to Location Sender
    addr = BASE_URI.format(vehicle.vin.lower())
    logger.info(f"Send data to {addr}")

    try:
        response = requests.post(addr, json=data, timeout=5)

        if response.ok:
            logger.info(f"Successful post to {vehicle.vin}. Status: {response.status_code}")
        else:
            logger.warning(f"Failed post to {vehicle.vin}. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request for {vehicle.vin} failed: {repr(e)}")

    # Send to Distance Monitor
    try:
        distance_monitor_url = f"http://distance-monitor-{vehicle.vin.lower()}/data"
        response = requests.post(distance_monitor_url, json=data, timeout=5)
        logger.info(f"Sent to Distance Monitor for {vehicle.vin}")
    except Exception as e:
        logger.debug(f"Distance Monitor request failed (this is ok if DM runs centrally): {e}")

# Simulate scenario: Vehicle 2 approaches Vehicle 1
def simulate_approach_scenario():
    """Simulate vehicle 2 approaching vehicle 1"""
    if len(vehicles) >= 2:
        # Make vehicle 2 faster than vehicle 1
        vehicles[0].velocity = 5   # 18 km/h
        vehicles[1].velocity = 10  # 36 km/h

        # Gradually decrease distance between vehicles
        if last_distances[vehicles[1].vin]['front'] > 5:
            # Simulate approaching by decreasing front distance
            last_distances[vehicles[1].vin]['front'] *= 0.9

# Main loop
logger.info("Starting Data Mock service...")
logger.info(f"Simulating {len(vehicles)} vehicles")

iteration = 0
while True:
    iteration += 1

    # Every 10 iterations, adjust scenario
    if iteration % 10 == 0:
        simulate_approach_scenario()

    # Update all vehicles
    for vehicle in vehicles:
        update_car(vehicle)

    time.sleep(2)