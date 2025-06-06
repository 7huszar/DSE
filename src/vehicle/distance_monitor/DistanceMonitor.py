import json
import os
import time

import requests
from flask import request, jsonify
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.vehicle.base_sender_service import BaseSenderService

class DistanceMonitorService(BaseSenderService):

    def __init__(self):
        self.change_rate = 0.0
        self.last_dst_front = 0.0
        self.vin: str = os.environ.get("VIN")
        super().__init__()

    def send_data(self, addr: str, data):
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
        data = request.get_json()
        self.logger.info(f"Received data: {str(data)}")

        if self.last_dst_front != 0.0:
            self.change_rate = self.last_dst_front - float(data["dst_front"])

        dst_front = float(data["dst_front"])
        if dst_front < 10.0 and self.change_rate > 5.0:
            trigger_data = {
                "time": time.time()
            }
            self.logger.info(f"Trigger emergency brake, because frontal distance is {dst_front} < 16.0")
            self.send_data(f"http://emergency-brake-{self.vin.lower()}/trigger", trigger_data)

        try:
            new_data = {
                "vin": data["vin"],
                "dst_front": data["front_dst"],
                "time": data["time"],
                "change_rate": self.change_rate
            }
            self.channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.distance_monitor',
                body=json.dumps(new_data).encode("utf-8")
            )

        except (AMQPConnectionError, AMQPChannelError) as e:
            self.logger.warning(f"Failed to send message to broker with routing key: 'backend.location.distance_monitor' because of connection/channel error: {repr(e)}")
            self.retry_queue.put(data)
            with self.connection_dead:
                self.connection_dead.notify_all()

        return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    service = DistanceMonitorService()
    service.log_stats()
    service.run()