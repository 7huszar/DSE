import json
from flask import request, jsonify
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.vehicle.base_sender_service import BaseSenderService

class LocationSenderService(BaseSenderService):

    def receive_data(self):
        data = request.get_json()
        self.logger.info(f"Received data: {str(data)}")

        try:
            self.channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.tracker',
                body=json.dumps(data).encode("utf-8")
            )

        except (AMQPConnectionError, AMQPChannelError) as e:
            self.logger.warning(f"Failed to send message to broker with routing key: 'backend.location.tracker' because of connection/channel error: {repr(e)}")
            self.retry_queue.put(data)
            with self.connection_dead:
                self.connection_dead.notify_all()

        try:
            self.channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.passenger',
                body=json.dumps(data).encode("utf-8")
            )

        except (AMQPConnectionError, AMQPChannelError) as e:
            self.logger.warning(f"Failed to send message to broker with routing key: 'backend.location.passenger' because of connection/channel error: {repr(e)}")
            self.retry_queue.put(data)
            with self.connection_dead:
                self.connection_dead.notify_all()

        return jsonify({"status": "ok"}), 200

    def get_retry_routing_key(self):
        return "backend.location.tracker"


if __name__ == '__main__':
    LocationSenderService().run()