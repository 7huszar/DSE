import json
import os
import time

import logging

from vehicle import Vehicle
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


with open("vehicles.json", "r") as f:
    vehicle_config = json.load(f)

### CONSTANTS START ###

BASE_URI = "http://location-sender-{}/data"

MAX_DST_FRONT = float(os.environ.get("MAX_DST_FRONT", 50))

MIN_DST_FRONT = float(os.environ.get("MIN_DST_FRONT", 0.5))

MAX_DST_BACK = float(os.environ.get("MAX_DST_BACK", 50))
MIN_DST_BACK = float(os.environ.get("MIN_DST_BACK", 0.5))

SAMPLING_TIME = int(os.environ.get("SAMPLING_TIME", 2))

### CONSTANTS END ###

logger.info("Started data mock with configuration:\n"
            f"MAX_DST_FRONT: {MAX_DST_FRONT}, "
            f"MIN_DST_FRONT: {MIN_DST_FRONT}, "
            f"MAX_DST_BACK: {MAX_DST_BACK}, "
            f"MIN_DST_BACK: {MIN_DST_BACK}, "
            f"SAMPLING_TIME: {SAMPLING_TIME}")

vehicles = []
for vehicle in vehicle_config:
    vehicles.append(
        Vehicle(
            vin=vehicle["vin"],
            velocity=vehicle["vel"],
            longitude=vehicle["lon"],
            latitude=vehicle["lat"],
            direction=vehicle["dir"],
            dst_back=vehicle["dst_back"],
            dst_front=vehicle["dst_front"]
        )
    )

print("Init data mock with car:")
for vehicle in vehicles:
    print(vehicle)

def update_car(vehicle):

    new_coord = vehicle.sample(0, 0)

    data = {
            "vin": vehicle.vin,
            "lat": new_coord[0],
            "long": new_coord[1],
            "time": new_coord[2],
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
    time.sleep(SAMPLING_TIME)