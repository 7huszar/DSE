import json
from flask import request, jsonify
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.vehicle.base_sender_service import BaseSenderService

#This Service implements the Location Sender Service in the vehicle
class LocationSenderService(BaseSenderService):

    def receive_data(self):
        #Receive location data from data mock, as subsitute for real GPS locator
        data = request.get_json()
        self.logger.info(f"Received data: {str(data)}")

        try:
            #Publish location to backend location tracker
            self.channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.tracker',
                body=json.dumps(data).encode("utf-8")
            )

            #Publish location to frontend visor
            self.channel.basic_publish(
                exchange='broker',
                routing_key='visor.location',
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
    service = LocationSenderService()
    service.log_stats()
    service.run()