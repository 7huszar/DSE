import time

import logging

from vehicle_module import Vehicle
import requests
import random
import numpy as np

### CONSTANTS START ###

BASE_URI = "http://location-sender-{}/data"
VINS = ["4A3AK24FX6E028812", "1N6SD16S8NC343640"]

MAX_DISTANCE_FRONT = 50 #in m
MIN_DISTANCE_FRONT = 0.5

MAX_DISTANCE_BACK = 50
MIN_DISTANCE_BACK = 0.5

MAX_CHANGE_RATE_PERCENT = 0.05

last_distance_back = 0
last_distance_front = 0

### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

vehicles = []
for vin in VINS:
    vehicles.append(Vehicle(vin, velocity=1.0, longitude=48.192701205090565, latitude=16.37814270634505, direction=[0.0, 1.0]))

def update_car(vehicle):

    new_coord = vehicle.sample(48.192701205090565, 16.37814270634505)

    distance_front = random.sample(np.arange(MIN_DISTANCE_FRONT, MAX_DISTANCE_FRONT, 0.1),1)[0]
    distance_back = random.sample(np.arange(MIN_DISTANCE_BACK, MAX_DISTANCE_BACK, 0.1),1)[0]

    while(distance_front < MIN_DISTANCE_FRONT or distance_front > MAX_DISTANCE_FRONT):
        distance_front = random.sample(np.arange(MIN_DISTANCE_FRONT, MAX_DISTANCE_FRONT, 0.1),1)[0]




    distance_back = random.sample(np.arange(MIN_DISTANCE_BACK, MAX_DISTANCE_BACK, 0.1),1)[0]

    last_distance_front = distance_front
    last_distance_back = distance_back

    data = {
            "vin": vehicle.vin,
            "lat": new_coord[0],
            "long": new_coord[1],
            "time": new_coord[2],
            "distance_front": distance_front,
            "distance_back": distance_back
    }

    logger.info(f"Send data to {vehicle.vin} with body:{str(data)}")

    try:
        response = requests.post(BASE_URI.format(vehicle.vin.lower()), json=data, timeout=5)

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