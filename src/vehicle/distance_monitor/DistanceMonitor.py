import json
import os
import time

import requests
from flask import request, jsonify
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.vehicle.base_sender_service import BaseSenderService

#This Service is identical in the vehicle and the backend. At deployment, it takes the deployment location as an argument

class DistanceMonitorService(BaseSenderService):

    def __init__(self):
        self.change_rate = 0.0
        self.last_dst_front = 0.0
        self.vin: str = os.environ.get("VIN")
        super().__init__()

    def send_data(self, addr: str, data):
        #Send distance moni
        self.logger.info(f"Send data to {addr} with body:{str(addr)}")

        try:
            response = requests.post(addr, json=data, timeout=5)
            if response.ok:
                self.logger.info(f"Successful post request to {addr}. \nResponse status: {response.status_code}\n Response body: {response.text}")
            else:
                self.logger.warning(f"Failed post request to {addr}. \nResponse status: {response.status_code}\n Response body: {response.text}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request for {addr} failed:\n{repr(e)}")


    def receive_data(self):
        #Receive data from data mock
        data = request.get_json()
        self.logger.info(f"Received data: {str(data)}")
        dst_front = float(data["dst_front"])

        if self.last_dst_front != 0.0:
            self.change_rate = self.last_dst_front - dst_front
        self.last_dst_front = dst_front

        self.logger.info(self.change_rate)
        if dst_front < 10.0 and self.change_rate > 4.0:
            trigger_data = {
                "time": time.time(),
                "vin": self.vin
            }
            #If it is deployed in the vehicle, send emergency brake command to vehicle service via HTTP. Otherwise to the central director
            self.logger.info(f"Trigger emergency brake, because frontal distance is {dst_front} < 16.0")
            if os.environ.get("SERVICE_DEPLOYMENT_LOCATION") == "vehicle":
                self.send_data(f"http://emergency-brake-{self.vin.lower()}/trigger", trigger_data)
            if os.environ.get("SERVICE_DEPLOYMENT_LOCATION") == "backend":
                self.send_data(f"http://central-director-service/emergency", trigger_data)

        try:
            #Send distance data via RabbitMQ to the frontend visor to display there
            new_data = {
                "vin": data["vin"],
                "dst_front": data["dst_front"],
                "time": data["time"],
                "change_rate": self.change_rate
            }
            self.channel.basic_publish(
                exchange='broker',
                routing_key="visor.distance",
                body=json.dumps(new_data).encode("utf-8")
            )

        except (AMQPConnectionError, AMQPChannelError) as e:
            self.logger.warning(f"Failed to send message to broker with routing key: 'visor.distance' because of connection/channel error: {repr(e)}")
            self.retry_queue.put(data)
            with self.connection_dead:
                self.connection_dead.notify_all()

        return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    service = DistanceMonitorService()
    service.log_stats()
    service.run()