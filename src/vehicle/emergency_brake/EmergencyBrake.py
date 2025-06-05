import json
import os
import threading

from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.vehicle.base_rabbitmq_connection import BaseRabbitMqConnection

from flask import Flask, jsonify, request
import requests

class EmergencyBrake(BaseRabbitMqConnection):

    def __init__(self):
        super().__init__(True)

        self.vin: str = os.getenv("VIN").lower()
        self.app = Flask(__name__)
        self.addr: str = f"http://data-mock/brake/{self.vin.upper()}"
        self.timout: float = float(os.getenv("TIMEOUT", 5))
        self.time_lock = threading.Lock()
        self.brake_lock = threading.Lock()
        self.last_brake_time: float = 0

        self.FLASK_HOST: str = os.environ.get("FLASK_HOST", "0.0.0.0")
        self.FLASK_PORT: int = int(os.environ.get("FLASK_PORT", 5000))

        self.consumer_connection = None
        self.consumer_channel = None

        self.app.add_url_rule("/trigger", view_func=self.brake, methods=["POST"])

        super().run()
        self.channel.exchange_declare(exchange='broker', exchange_type='topic', durable=True)
        result = self.channel.queue_declare('', exclusive=False)
        self.queue_name: str = result.method.queue

        self.app.add_url_rule('/shutdown', 'flask_shutdown', self.flask_shutdown, methods=['POST'])

        self.flask_thread = threading.Thread(target=self.run_flask, daemon=False)
        self.consumer_thread = threading.Thread(target=self.consume, daemon=False)

    def run_flask(self):
        self.app.run(host=self.FLASK_HOST, port=self.FLASK_PORT)


    def brake(self):
        self.logger.info(f"Requested emergency break by http request for {self.vin}")
        data = request.get_json()
        return self.trigger_brake(data.get("time"))

    def trigger_brake(self, time):
        with self.brake_lock:

            with self.time_lock:
                if self.last_brake_time > time:
                    return jsonify({"status": "conflict"}), 409

            try:
                response = requests.post(self.addr, timeout=self.timout)
                if response.ok:
                    with self.time_lock:
                        self.last_brake_time = float(response.json().get("time"))

                    self.logger.info(f"Successful post request to {self.addr}. \nResponse status: {response.status_code}\n Response body: {response.text}")
                    self.logger.info(f"Triggered emergency break for {self.vin}")
                    self.publish(data=response.json())
                else:
                    self.logger.warning(f"Failed post request to {self.addr}. \nResponse status: {response.status_code}\n Response body: {response.text}")
                    return jsonify(response.json()), response.status_code
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request for {self.addr} failed:\n{repr(e)}")
                return jsonify({"status": "internal server error"}), 500

            return jsonify({"status": "ok"}), 200

    def publish(self, data):
        self.logger.info("Send ack of triggered emergency break.")

        try:
            self.channel.basic_publish(
                exchange='broker',
                routing_key='backend.location.tracker',
                body=json.dumps(data).encode("utf-8")
            )
        except (AMQPConnectionError, AMQPChannelError) as e:
            self.logger.warning(f"Failed to send message to broker with routing key: 'backend.location.distance_monitor' because of connection/channel error: {repr(e)}")
            self.retry_queue.put(data)
            with self.connection_dead:
                self.connection_dead.notify_all()


    def run(self):
        super().run()

        self.channel.queue_bind(exchange='broker', queue=self.queue_name, routing_key='vehicle.emergency_break')
        self.consumer_thread.start()
        self.flask_thread.start()

    def callback(self, ch, method, properties, body):
        self.logger.info(f"Requested emergency brake by async rabbitmq for {self.vin}")
        self.trigger_brake(json.loads(body.decode("utf-8")).get("time"))

    def consume(self):
        self.consumer_connection = self.get_rabbitmq_connection()
        self.consumer_channel = self.consumer_connection.channel()

        self.consumer_channel.queue_bind(exchange='broker', queue=self.queue_name, routing_key='vehicle.emergency_break')

        self.consumer_channel.basic_consume(queue=self.queue_name, on_message_callback=self.callback, auto_ack=True)

        self.logger.info("Started RabbitMQ consumer thread.")
        try:
            self.consumer_channel.start_consuming()
        except Exception as e:
            self.logger.error(f"Consumer stopped due to exception: {repr(e)}")
        finally:
            if self.consumer_channel and not self.consumer_channel.is_closed:
                self.consumer_channel.close()
            if self.consumer_connection and not self.consumer_connection.is_closed:
                self.consumer_connection.close()

    def flask_shutdown(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()
        return 'Server shutting down...', 200


    def shutdown(self):
        try:
            requests.post(f"http://{self.FLASK_HOST}:{self.FLASK_PORT}/shutdown", timeout=1)
        except Exception as e:
            self.logger.info(f"Flask shutdown request failed (probably normal if already shutting down): {repr(e)}")

        if self.flask_thread and self.flask_thread.is_alive():
            self.flask_thread.join(1)

        if self.consumer_channel and self.consumer_channel.is_open:
            try:
                self.logger.info("Stopping consumer channel...")
                self.consumer_channel.stop_consuming()
            except Exception as e:
                self.logger.warning(f"Failed to stop consumer channel: {repr(e)}")

        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread.join(1)

        super().shutdown()


if __name__ == "__main__":
    service = EmergencyBrake()
    service.log_stats()
    service.run()
