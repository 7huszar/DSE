import json
import os
import time

import logging

from vehicle import Vehicle
import requests
from flask import Flask
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
print("Init data mock with car(s):")
for vehicle in vehicles:
    print(vehicle)

@app.route("/break/<vin>", methods=["POST"])
def trigger_break(vin: str):
    vehicles.get(vin).sample(acceleration=BRAKE_DECELERATION)


def update_car(vehicle):

    new_coord = vehicle.sample()

    data = {
            "vin": vehicle.vin,
            "lat": float(new_coord["lat"]),
            "long": float(new_coord["long"]),
            "time": float(new_coord["internal_time"]),
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

while True:
    for vehicle in vehicles.values():
        update_car(vehicle)
    time.sleep(SAMPLING_TIME)
