import json
import os
import threading
import time
import logging
from vehicle import Vehicle
import requests
from flask import Flask, jsonify
import numpy as np
import importlib



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
BASE_URI_MON = "http://distance-monitor-{vin}-{location}/data"

MAX_DST_FRONT = float(os.environ.get("MAX_DST_FRONT", 50))

MIN_DST_FRONT = float(os.environ.get("MIN_DST_FRONT", 0.5))

MAX_DST_BACK = float(os.environ.get("MAX_DST_BACK", 50))
MIN_DST_BACK = float(os.environ.get("MIN_DST_BACK", 0.5))

SAMPLING_TIME = int(os.environ.get("SAMPLING_TIME", 2))

TIMEOUT = int(os.environ.get("TIMOUT", 5))

SCENARIO = os.getenv("SCENARIO")

scenario_module = importlib.import_module(f"scenarios.{SCENARIO}")

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
        dst_front=vehicle["dst_front"]
    )
    for vehicle in vehicle_config
}



print("Init data mock with car(s):")
for vehicle in vehicles:
    print(vehicle.__str__())

@app.route("/brake/<vin>", methods=["POST"])
def trigger_break(vin: str):
    logger.info(f"Emergency break triggered for {vin}")
    vehicles.get(vin).velocity = 0.0
    vehicles[vin].acceleration = 0.0
    return jsonify({"vin": vin, "time": time.time()}), 200

def send_data(addr: str, data):
    logger.info(f"Send data to {addr} with body:{data}")

    try:
        response = requests.post(addr, json=data, timeout=TIMEOUT)
        if response.ok:
            logger.info(f"Successful post request to {addr}. \nResponse status: {response.status_code}\n Response body: {response.text}")
        else:
            logger.warning(f"Failed post request to {addr}. \nResponse status: {response.status_code}\n Response body: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request for {addr} failed:\n{repr(e)}")



def update_car(vehicle):
    """Update vehicle position and send data"""

    scenario_module.mess_with_vehicle(vehicle)

    # Get new position
    new_coord = vehicle.sample()

    front_dst = scenario_module.compute_dst_front(vehicle)

    data_loc = {
            "vin": vehicle.vin,
            "lat": float(new_coord["lat"]),
            "lon": float(new_coord["lon"]),
            "time": float(new_coord["internal_time"]),
            "speed": vehicle.velocity * 3.6
    }

    addr_loc = BASE_URI_LOC.format(vehicle.vin.lower())

    send_data(addr_loc, data_loc)

    data_mon = {
        "vin": vehicle.vin,
        "dst_front": front_dst,
        "speed": vehicle.velocity * 3.6,
        "time": time.time()
    }

    addr_mon_vehicle = BASE_URI_MON.format(vin=vehicle.vin.lower(), location="vehicle")
    addr_mon_backend = BASE_URI_MON.format(vin=vehicle.vin.lower(), location="backend")
    send_data(addr_mon_vehicle, data_mon)
    logger.info("Sent data to distance monitor vehicle!")
    send_data(addr_mon_backend, data_mon)
    logger.info("Sent data to distance monitor backend!")

threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 5000}, daemon=True).start()
time.sleep(5)
while True:
    for vehicle in vehicles.values():
        update_car(vehicle)
    time.sleep(SAMPLING_TIME)
