import json
import time

import logging

from vehicle import Vehicle
import requests
import random
import numpy as np

vehicle_config = None
with open("vehicles.json", "r") as f:
    vehicle_config = json.load(f)

### CONSTANTS START ###

BASE_URI = "http://location-sender-{}/data"

MAX_DISTANCE_FRONT = 50 #in m
MIN_DISTANCE_FRONT = 0.5

MAX_DISTANCE_BACK = 50
MIN_DISTANCE_BACK = 0.5

MAX_CHANGE_RATE_PERCENT = 0.15

last_distance_back = 0
last_distance_front = 0

### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

vehicles = []
for vehicle in vehicle_config:
    vehicles.append(Vehicle(vehicle["vin"], velocity=vehicle["vel"], longitude=vehicle["lon"], latitude=vehicle["lat"], direction=vehicle["dir"]))

def update_car(vehicle):

    global last_distance_front
    global last_distance_back

    new_coord = vehicle.sample(0, 0)

    if last_distance_front == 0:
        distance_front = random.choice(np.arange(MIN_DISTANCE_FRONT, MAX_DISTANCE_FRONT, 0.1))
    else:
        distance_front = 0
        while distance_front < MIN_DISTANCE_FRONT or distance_front > MAX_DISTANCE_FRONT:
            distance_front = random.choice(np.arange((1-MAX_CHANGE_RATE_PERCENT)*last_distance_front,(1+MAX_CHANGE_RATE_PERCENT)*last_distance_front, 0.1))

    last_distance_front = distance_front

    if last_distance_back == 0:
        distance_back = random.choice(np.arange(MIN_DISTANCE_BACK, MAX_DISTANCE_BACK, 0.1))
    else:
        distance_back = 0
        while distance_back < MIN_DISTANCE_BACK or distance_back > MAX_DISTANCE_BACK:
            distance_back = random.choice(np.arange((1-MAX_CHANGE_RATE_PERCENT)*last_distance_back,(1+MAX_CHANGE_RATE_PERCENT)*last_distance_back, 0.1))

    last_distance_back = distance_back

    logger.info(f"Distance front: {distance_front} m, distance back: {distance_back}")


    data = {
            "vin": vehicle.vin,
            "lat": new_coord[0],
            "long": new_coord[1],
            "time": new_coord[2],
            "distance_front": distance_front,
            "distance_back": distance_back
    }


    addr = BASE_URI.format(vehicle.vin.lower())
    logger.info(f"Send data to {addr} with body:{str(data)}")

    try:
        response = requests.post(addr, json=data, timeout=5)

        if response.ok:
            logger.info(f"Successful post request to {vehicle.vin}. \nResponse status: {response.status_code}\n Response body: {response.text}")
        else:
            logger.warning(f"Failed post request to {vehicle.vin}. \nResponse status: {response.status_code}\n Response body: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request for {vehicle.vin} failed:\n{repr(e)}")

while True:
    for vehicle in vehicles:
        update_car(vehicle)
    time.sleep(2)