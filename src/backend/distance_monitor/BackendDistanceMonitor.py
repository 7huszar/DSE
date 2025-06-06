import json
import os
import pika
import logging

import requests

class DistanceMonitorService:

    def __init__(self):
        self.vin: str = os.environ.get("VIN")

        self.RABBITMQ_USER = os.environ['RABBITMQ_USER']
        self.RABBITMQ_PWD = os.environ['RABBITMQ_PASSWORD']
        self.RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
        self.RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
        self.RETRY_WAIT = int(os.getenv("RETRY_WAIT", 5))
        self.credentials = pika.PlainCredentials(
            username=self.RABBITMQ_USER,
            password=self.RABBITMQ_PWD
        )

        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        )

        self.logger.info(f"Initiated Distance Monitor for Vehicle with VIN {self.vin.upper()}")
        self.consumer_connection = None
        self.consumer_channel = None

    def get_rabbitmq_connection(self):
        return pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.RABBITMQ_HOST,
                port=self.RABBITMQ_PORT,
                credentials=self.credentials
            )
        )

    def callback(self, ch, method, properties, body):
        payload = json.loads(body.decode("UTF-8"))
        self.logger.info(f"Received message: {payload}")
        if payload["dst_front"] < 10.0 or  payload["change_rate"] > 5.0:
            self.trigger_brake()

    def trigger_brake(self):
        self.logger.info("Triggered Emergency Brake in Backend Distance Monitor!")
        r = requests.post('http://central-director-service/emergency', json={"vin": self.vin})
        self.logger.info("Post Request with status code: " + str(r.status_code))

    def receive_data(self):
        self.consumer_connection = self.get_rabbitmq_connection()
        if(self.consumer_connection == None):
            self.logger.error("Could not establish connection to RabbitMQ!")
        self.consumer_channel = self.consumer_connection.channel()


        routing_key = os.environ.get("DISTANCE_MONITOR_BACKEND").format(vin=self.vin.upper())

        self.logger.info(f"Routing key: {routing_key}")

        self.consumer_channel.queue_declare('', exclusive=False)
        self.consumer_channel.exchange_declare(exchange=os.environ.get("BROKER_EXCHANGE"), exchange_type='topic', durable=True)
        self.consumer_channel.queue_bind('',exchange=os.environ.get("BROKER_EXCHANGE"), routing_key=routing_key)
        self.consumer_channel.basic_consume('', on_message_callback=self.callback, auto_ack=True)

        self.logger.info("Started RabbitMQ consumer!")

        try:
            self.consumer_channel.start_consuming()
        except Exception as e:
            self.logger.error(f"Consumer stopped due to exception: {repr(e)}")
        finally:
            if self.consumer_channel and not self.consumer_channel.is_closed:
                self.consumer_channel.close()
            if self.consumer_connection and not self.consumer_connection.is_closed:
                self.consumer_connection.close()

    def shutdown(self):
        if self.consumer_channel and self.consumer_channel.is_open:
            try:
                self.logger.info("Stopping consumer channel...")
                self.consumer_channel.stop_consuming()
            except Exception as e:
                self.logger.warning(f"Failed to stop consumer channel: {repr(e)}")


if __name__ == '__main__':
    service = DistanceMonitorService()
    service.receive_data()