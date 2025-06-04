import threading
import os
from flask import Flask
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.vehicle.base_rabbitmq_connection import BaseRabbitMqConnection


class BaseSenderService(BaseRabbitMqConnection):

    def __init__(self):
        super().__init__(True)
        self.connection = None
        self.channel = None

        self.FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
        self.FLASK_PORT = int(os.environ.get("FLASK_PORT", 5000))

        self.app = Flask(__name__)
        self.app.add_url_rule('/data', 'receive_data', self.receive_data, methods=['POST'])

    def run(self):
        super().run()

        threading.Thread(target=self.process_failed_msg, daemon=True).start()
        threading.Thread(target=self.reestablish_connection, daemon=True).start()

        self.app.run(host=self.FLASK_HOST, port=self.FLASK_PORT)

    def receive_data(self):
        """Override this in subclasses"""
        raise NotImplementedError("Subclasses must implement receive_data()")

    def get_env_variables(self):
        return f"FLASK_HOST: {self.FLASK_HOST}, FLASK_PORT: {self.FLASK_PORT}, {super().get_env_variables()}"

