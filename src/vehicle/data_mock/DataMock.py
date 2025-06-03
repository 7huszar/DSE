import json
import os
import time
import logging
from vehicle import Vehicle
import requests
from flask import Flask
import random
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("DataMock")

app = Flask(__name__)

with open("vehicles.json", "r") as f:
    vehicle_config = json.load(f)

### CONSTANTS START ###

BASE_URI_LOC = "http://location-sender-{}/data"
BASE_URI_MON = "http://distance-monitor-{}/data"

MAX_DST_FRONT = float(os.environ.get("MAX_DST_FRONT", 50))

MIN_DST_FRONT = float(os.environ.get("MIN_DST_FRONT", 0.5))

MAX_DST_BACK = float(os.environ.get("MAX_DST_BACK", 50))
MIN_DST_BACK = float(os.environ.get("MIN_DST_BACK", 0.5))

SAMPLING_TIME = int(os.environ.get("SAMPLING_TIME", 2))

TIMEOUT = int(os.environ.get("TIMOUT", 5))

BRAKE_DECELERATION = float(os.environ.get("BRAKE_DECELERATION", -10.0))
# Vehicle-specific last distances (using VIN as key)
last_distances = {}

### CONSTANTS END ###

logger.info("Started data mock with configuration:\n"
            f"MAX_DST_FRONT: {MAX_DST_FRONT}, "
            f"MIN_DST_FRONT: {MIN_DST_FRONT}, "
            f"MAX_DST_BACK: {MAX_DST_BACK}, "
            f"MIN_DST_BACK: {MIN_DST_BACK}, "
            f"SAMPLING_TIME: {SAMPLING_TIME}, "
            f"TIMOUT: {TIMEOUT}, "
            f"BRAKE_DECELERATION: {BRAKE_DECELERATION}")

vehicles = {
    vehicle["vin"]: Vehicle(
        vin=vehicle["vin"],
        velocity=vehicle["vel"],
        longitude=vehicle["lon"],
        latitude=vehicle["lat"],
        direction=np.array(vehicle["dir"], dtype=float),
        dst_back=vehicle["dst_back"],
        dst_front=vehicle["dst_front"]
    )
    for vehicle in vehicle_config
}

last_distances[v.vin] = {
    'front': float(os.environ.get("LAST_DST_FRONT", 0)),
    'back': float(os.environ.get("LAST_DST_BACK", 0))
}


print("Init data mock with car(s):")
for vehicle in vehicles:
    print(vehicle)

@app.route("/break/<vin>", methods=["POST"])
def trigger_break(vin: str):
    vehicles.get(vin).sample(acceleration=BRAKE_DECELERATION)


def update_car(vehicle):
    """Update vehicle position and send data"""
    vin = vehicle.vin
    last_front = last_distances[vin]['front']
    last_back = last_distances[vin]['back']

    new_coord = vehicle.sample()

    # Get new position
    new_coord = vehicle.sample(0, 0)

    # Calculate front distance
    if last_front == 0:
        distance_front = random.choice(np.arange(MIN_DST_FRONT, MAX_DST_FRONT, 0.1))
    else:
        distance_front = 0
        while distance_front < MIN_DST_FRONT or distance_front > MAX_DST_FRONT:
            min_range = max(MIN_DST_FRONT, (1-0.05)*last_front)
            max_range = min(MAX_DST_FRONT, (1+0.05)*last_front)
            distance_front = random.choice(np.arange(min_range, max_range, 0.1))

    # Calculate back distance
    if last_back == 0:
        distance_back = random.choice(np.arange(MIN_DST_BACK, MAX_DST_BACK, 0.1))
    else:
        distance_back = 0
        while distance_back < MIN_DST_BACK or distance_back > MAX_DST_BACK:
            min_range = max(MIN_DST_BACK, (1-0.05)*last_back)
            max_range = min(MAX_DST_BACK, (1+0.05)*last_back)
            distance_back = random.choice(np.arange(min_range, max_range, 0.1))

    # Update last distances
    last_distances[vin]['front'] = distance_front
    last_distances[vin]['back'] = distance_back

    logger.info(f"Vehicle {vin}: Distance front: {distance_front:.1f}m, back: {distance_back:.1f}m, speed: {vehicle.velocity*3.6:.1f} km/h")

    # Prepare data with speed
    data = {
            "vin": vehicle.vin,
            "lat": float(new_coord["lat"]),
            "long": float(new_coord["long"]),
            "time": float(new_coord["internal_time"]),
        "distance_front": distance_front,
        "distance_back": distance_back,
        "speed": vehicle.velocity * 3.6  # Convert m/s to km/h

    }


    addr_loc = BASE_URI_LOC.format(vehicle.vin.lower())
    logger.info(f"Send data to {addr_loc} with body:{str(data)}")

    try:
        response = requests.post(addr_loc, json=data, timeout=TIMEOUT)

        if response.ok:
            logger.info(f"Successful post request to {addr_loc}. \nResponse status: {response.status_code}\n Response body: {response.text}")
        else:
            logger.warning(f"Failed post request to {addr_loc}. \nResponse status: {response.status_code}\n Response body: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request for {addr_loc} failed:\n{repr(e)}")

#    addr_mon = BASE_URI_MON.format(vehicle.vin.lower())
#
#    try:
#        response = requests.post(addr_mon, json={"dst_front": 7}, timeout=TIMEOUT)
#        if response.ok:
#           logger.info(f"Successful post request to {addr_mon}. \nResponse status: {response.status_code}\n Response body: {response.text}")
#        else:
#            logger.warning(f"Failed post request to {addr_mon}. \nResponse status: {response.status_code}\n Response body: {response.text}")
#    except requests.exceptions.RequestException as e:
#        logger.error(f"Request for {addr_mon} failed:\n{repr(e)}")


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


while True:
    for vehicle in vehicles.values():
        update_car(vehicle)
    time.sleep(SAMPLING_TIME)
