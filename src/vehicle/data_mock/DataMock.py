import time

import logging

from vehicle_module import Vehicle
import requests

### CONSTANTS START ###

RECEIVER = "http://location-sender-service/data"

### CONSTANTS END ###

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

vehicle = Vehicle(velocity=1.0, longitude=48.192701205090565, latitude=16.37814270634505, direction=[0.0, 1.0])

def update_car():
    global vehicle
    new_coord = vehicle.sample(48.192701205090565, 16.37814270634505)

    data = {
            "vin": "JMZBLA4G601934983",
            "lat": new_coord[0],
            "long": new_coord[1],
            "time": new_coord[2]
    }
    logger.info(f"Send data to {RECEIVER} with body:{str(data)}")

    try:
        response = requests.post(RECEIVER, json=data, timeout=5)

        if response.ok:
            logger.info(f"Successful post request to {RECEIVER}. \nResponse status: {response.status_code}\n Response body: {response.text}")
        else:
            logger.warning(f"Failed post request to {RECEIVER}. \nResponse status: {response.status_code}\n Response body: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request for {RECEIVER} failed:\n{repr(e)}")

while True:
    update_car()
    time.sleep(2)