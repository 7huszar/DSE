import threading
import time
import os
import json
import queue
from flask import Flask
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.vehicle.base_rabbitmq_connection import BaseRabbitMqConnection


class BaseSenderService(BaseRabbitMqConnection):

    def __init__(self):
        super().__init__()
        self.connection = None
        self.channel = None
        self.retry_queue = queue.Queue()
        self.connection_dead = threading.Condition()

        self.FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
        self.FLASK_PORT = int(os.environ.get("FLASK_PORT", 5000))

        self.app = Flask(__name__)
        self.app.add_url_rule('/data', 'receive_data', self.receive_data, methods=['POST'])

    def process_failed_msg(self):
        while True:
            with self.retry_queue.not_empty:
                while self.retry_queue.empty():
                    self.retry_queue.not_empty.wait()

            if self.channel.is_closed or self.connection.is_closed:
                with self.connection_dead:
                    self.connection_dead.notify_all()
                time.sleep(self.RETRY_WAIT)
                continue

            self.logger.info("Try to resend all failed msg.")
            while not self.retry_queue.empty():
                pkg = self.retry_queue.get()

                try:
                    self.channel.basic_publish(
                        exchange='broker',
                        routing_key=self.get_retry_routing_key(),
                        body=json.dumps(pkg).encode("utf-8")
                    )
                except (AMQPChannelError, AMQPConnectionError) as e:
                    self.logger.warning(f"Failed to resend msg: {repr(e)}")
                    with self.connection_dead:
                        self.connection_dead.notify_all()
                    self.retry_queue.put(pkg)
                    break

    def run(self):
        super().run()

        threading.Thread(target=self.process_failed_msg, daemon=True).start()
        threading.Thread(target=self.reestablish_connection, daemon=True).start()

        self.app.run(host=self.FLASK_HOST, port=self.FLASK_PORT)

    def receive_data(self):
        """Override this in subclasses"""
        raise NotImplementedError("Subclasses must implement receive_data()")

    def get_retry_routing_key(self):
        raise NotImplementedError("Subclass must implement get_retry_routing_key")

    def get_env_variables(self):
        return f"FLASK_HOST: {self.FLASK_HOST}, FLASK_PORT: {self.FLASK_PORT}, {super().get_env_variables()}"

