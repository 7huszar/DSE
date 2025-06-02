import json

import requests
from flask import request, jsonify
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.vehicle.base_sender_service import BaseSenderService


class DistanceMonitorService(BaseSenderService):

    def __init__(self):
        self.vin: str = "tmp"
        super().__init__()


    def receive_data(self):
        data = request.get_json()
        self.logger.info(f"Received data: {str(data)}")

        dst_front = float(data["dst_front"])
        if dst_front < 0.5:
            requests.post(f"http://data-mock/break/{self.vin}")

        try:
            self.channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.distance_monitor',
                body=json.dumps(data).encode("utf-8")
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