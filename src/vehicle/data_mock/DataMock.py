import time

import logging

from vehicle_module import Vehicle
import requests

### CONSTANTS START ###

BASE_URI = "http://location-sender-{}/data"
VINS = ["4A3AK24FX6E028812", "1N6SD16S8NC343640"]
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

    data = {
            "vin": vehicle.vin,
            "lat": new_coord[0],
            "long": new_coord[1],
            "time": new_coord[2]
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