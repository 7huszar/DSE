import time

import Vehicle
import requests

vehicle = Vehicle(velocity=1.0, longitude=48.192701205090565, latitude=16.37814270634505, direction=[0.0, 1.0])

def update_car():
    global vehicle
    while True:
        new_coord = vehicle.sample()

        data = {
            "vin": "JMZBLA4G601934983",
            "lat": new_coord[0],
            "long": new_coord[1],
            "time": new_coord[3]
        }

        requests.post("http://location-sender-service:5000/data", json=data)
        print("sent")
        time.sleep(1)

