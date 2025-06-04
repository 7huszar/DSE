import os

from src.vehicle.base_rabbitmq_connection import BaseRabbitMqConnection

from flask import Flask
import requests

class EmergencyBrake(BaseRabbitMqConnection):

    def __init__(self):
        super().__init__()
        self.vin = "tmp"
        self.app = Flask(__name__)

        self.FLASK_HOST: str = os.environ.get("FLASK_HOST", "0.0.0.0")
        self.FLASK_PORT: int = int(os.environ.get("FLASK_PORT", 5000))

        self.app.add_url_rule("/trigger", view_func=self.trigger_brake, methods=["POST"])

    def trigger_brake(self):
        requests.post(f"http://data-mock/{self.vin}")


    def run(self):
        super().run()

        self.app.run(host=self.FLASK_HOST, port=self.FLASK_PORT)

if __name__ == "__main__":
    service = EmergencyBrake()
    service.log_stats()
    service.run()
