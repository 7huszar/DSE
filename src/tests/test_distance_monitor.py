import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import os


from src.vehicle.distance_monitor.DistanceMonitor import DistanceMonitorService

from flask import Flask

class TestDistanceMonitorServiceREST(unittest.TestCase):

    def setUp(self):
        # Setup env variables
        os.environ["VIN"] = "TESTVIN123"
        os.environ["SERVICE_DEPLOYMENT_LOCATION"] = "vehicle"
        os.environ["EMERGENCY_BRAKE_BASE_URI"] = "http://fake_emergency_brake_service:80/trigger"
        os.environ["CENTRAL_DIRECTOR_URI"] = "http://fake_central_director:80/emergency"
        os.environ["RABBITMQ_HOST"] = "fake_rabbitmq_host"
        os.environ["RABBITMQ_PORT"] = str(102030)
        os.environ["RABBITMQ_USER"] = "fake_rabbitmq_user"
        os.environ["RABBITMQ_PASSWORD"] = "fake_rabbitmq_pw"

        # Initialize service
        self.service = DistanceMonitorService()

        # Build Flask app and add route
        self.app = Flask(__name__)

        @self.app.route("/data", methods=["POST"])
        def data_endpoint():
            return self.service.receive_data()

        # Build test client
        self.client = self.app.test_client()

        # Mock channel so we don't publish
        self.service.channel = MagicMock()

    @patch("src.vehicle.distance_monitor.DistanceMonitor.requests.post")
    def test_receive_data_triggers_emergency_brake(self, mock_requests_post):
        # Simulate previous state -> Distance change is -9999 meters in 1 second -> Trigger emergency brake
        self.service.last_dst_front = 10000.0
        self.service.last_time = datetime(2025, 6, 8, 12, 0, 0, tzinfo=timezone.utc)

        # Mock requests.post to always return a successful response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        # Prepare test payload
        payload = {
            "vin": "TESTVIN123",
            "dst_front": 1.0,
            "dst_rear": 10.0,
            "time": "2025-06-08T12:00:01.000000+00:00",
            "speed":8000
        }

        # Send POST to test client
        response = self.client.post("/data", json=payload)

        # Check response
        self.assertEqual(response.status_code, 200)

        # Verify that REST endpoint was called
        mock_requests_post.assert_called_once()

        called_url = mock_requests_post.call_args[0][0]
        called_data = mock_requests_post.call_args[1]['json']

        print(f"call URL: {called_url}")
        print(f"call body: {called_data}")

        self.assertEqual(
            called_url,
            "http://fake_emergency_brake_service:80/trigger"
        )
        self.assertEqual(called_data["vin"], "TESTVIN123")

        print("Emergency brake REST endpoint was correctly called.")


    @patch("src.vehicle.distance_monitor.DistanceMonitor.requests.post")
    def test_receive_data_not_triggers_emergency_brake(self, mock_requests_post):

        # Simulate previous state -> Distance has not changed -> No Emergency Brake
        self.service.last_dst_front = 1.0
        self.service.last_time = datetime(2025, 6, 8, 12, 0, 0, tzinfo=timezone.utc)

        # Mock requests.post to always return a successful response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        # Prepare test payload
        payload = {
            "vin": "TESTVIN123",
            "dst_front": 1.0,
            "dst_rear": 10.0,
            "time": "2025-06-08T12:00:01.000000+00:00",
            "speed":8000
        }

        # Send POST to test client
        response = self.client.post("/data", json=payload)

        # Check response
        self.assertEqual(response.status_code, 200)

        # Verify that REST endpoint was called
        mock_requests_post.assert_not_called()

        print("Emergency brake REST endpoint was correctly NOT called.")

    @patch("src.vehicle.distance_monitor.DistanceMonitor.requests.post")
    def test_receive_data_triggers_backend_central_director(self, mock_requests_post):
        # Change environment to backend deployment location
        os.environ["SERVICE_DEPLOYMENT_LOCATION"] = "backend"

        # Simulate previous state -> Distance has changed -> No emergency brake in backend
        self.service.last_dst_front = 100000.0
        self.service.last_time = datetime(2025, 6, 8, 12, 0, 0, tzinfo=timezone.utc)

        # Mock requests.post to always return a successful response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        # Prepare test payload
        payload = {
            "vin": "TESTVIN123",
            "dst_front": 1.0,
            "dst_rear": 10.0,
            "time": "2025-06-08T12:00:01.000000+00:00",
            "speed":8000
        }

        # Send POST to test client
        response = self.client.post("/data", json=payload)

        # Check response
        self.assertEqual(response.status_code, 200)

        # Verify that REST endpoint was NOT called
        mock_requests_post.assert_called_once()

        #Assert that the correct endpoint was called
        called_url = mock_requests_post.call_args[0][0]
        self.assertEqual(called_url, "http://fake_central_director:80/emergency/testvin123")

        print("Emergency brake REST backend endpoint was correctly called.")

if __name__ == "__main__":
    unittest.main()
