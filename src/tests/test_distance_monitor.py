import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json
import os
import sys

# Mock the base_sender_service module before importing DistanceMonitor
sys.modules['src.vehicle.base_sender_service'] = MagicMock()
sys.modules['pika'] = MagicMock()
sys.modules['pika.exceptions'] = MagicMock()

# Import after mocking dependencies
from src.vehicle.distance_monitor.DistanceMonitor import DistanceMonitorService


class TestDistanceMonitor(unittest.TestCase):
    """Test cases for the Distance Monitor service"""

    def setUp(self):
        # 1) Env-Variablen
        os.environ['VIN'] = 'TEST001'
        os.environ['SERVICE_DEPLOYMENT_LOCATION'] = 'vehicle'
        os.environ['FLASK_HOST'] = '0.0.0.0'
        os.environ['FLASK_PORT'] = '5000'

        # 2) Mock-Channel
        self.mock_channel = Mock()

        # 3) Objekt anlegen ohne __init__
        self.service = DistanceMonitorService.__new__(DistanceMonitorService)

        # 4) Manuell alle Properties setzen
        self.service.channel = self.mock_channel
        self.service.logger = Mock()
        self.service.retry_queue = Mock()
        self.service.connection_dead = Mock()
        self.service.vin = 'TEST001'
        self.service.last_dst_front = 0.0
        self.service.last_time = datetime.now(timezone.utc)
        self.service.change_rate = 0.0
        self.service.delta_time = 1.0

    @patch('requests.post')
    def test_emergency_brake_triggered_on_vehicle(self, mock_post):
        """Test 1: Emergency brake is triggered when conditions are met on vehicle deployment"""
        # Arrange
        os.environ['SERVICE_DEPLOYMENT_LOCATION'] = 'vehicle'
        self.service.last_dst_front = 15.0  # Previous distance
        self.service.last_time = datetime.now(timezone.utc)

        # Mock successful emergency brake response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.text = "Emergency brake triggered"
        mock_post.return_value = mock_response

        # Test data that should trigger emergency brake
        test_data = {
            "vin": "TEST001",
            "dst_front": 8.0,  # Less than 10.0
            "speed": 50.0,
            "time": datetime.now(timezone.utc).isoformat(timespec="microseconds")
        }

        # Mock Flask request
        with patch('flask.request') as mock_request:
            mock_request.get_json.return_value = test_data

            # Act
            response, status_code = self.service.receive_data()

            # Assert
            # Check if emergency brake endpoint was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Verify the correct endpoint was called
            expected_url = f"http://emergency-brake-test001/trigger"
            self.assertEqual(call_args[0][0], expected_url)

            # Verify the payload
            payload = call_args[1]['json']
            self.assertEqual(payload['vin'], 'TEST001')
            self.assertIn('Vehicle approaching vehicle too fast', payload['rsn'])
            self.assertEqual(payload['src'], 'distance-monitor-test001-vehicle')

            # Verify RabbitMQ publish was called
            self.mock_channel.basic_publish.assert_called()

            # Verify response
            self.assertEqual(status_code, 200)
            self.assertEqual(response.json, {"status": "ok"})

    @patch('requests.post')
    def test_central_director_notification_on_backend(self, mock_post):
        """Test 2: Central Director is notified when emergency conditions are met on backend deployment"""
        # Arrange
        os.environ['SERVICE_DEPLOYMENT_LOCATION'] = 'backend'
        self.service.last_dst_front = 20.0  # Previous distance
        self.service.last_time = datetime.now(timezone.utc)

        # Mock successful central director response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.text = "Emergency notification received"
        mock_post.return_value = mock_response

        # Test data that should trigger emergency notification
        test_data = {
            "vin": "TEST001",
            "dst_front": 5.0,  # Less than 10.0 - critical distance
            "speed": 70.0,
            "time": datetime.now(timezone.utc).isoformat(timespec="microseconds")
        }

        # Mock Flask request
        with patch('flask.request') as mock_request:
            mock_request.get_json.return_value = test_data

            # Act
            response, status_code = self.service.receive_data()

            # Assert
            # Check if central director endpoint was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Verify the correct endpoint was called
            expected_url = "http://central-director-service/emergency"
            self.assertEqual(call_args[0][0], expected_url)

            # Verify the payload
            payload = call_args[1]['json']
            self.assertEqual(payload['vin'], 'TEST001')
            self.assertIn('Vehicle approaching vehicle too fast', payload['rsn'])
            self.assertEqual(payload['src'], 'distance-monitor-test001-backend')

            # Verify change rate calculation
            # change_rate = (20.0 - 5.0) / delta_time = 15.0 / delta_time
            self.assertGreater(self.service.change_rate, 4.0)

            # Verify RabbitMQ publish
            self.mock_channel.basic_publish.assert_called()
            rabbitmq_call = self.mock_channel.basic_publish.call_args
            self.assertEqual(rabbitmq_call[1]['exchange'], 'broker')
            self.assertEqual(rabbitmq_call[1]['routing_key'], 'visor.distance')

            # Verify the published data includes change_rate
            published_data = json.loads(rabbitmq_call[1]['body'].decode('utf-8'))
            self.assertEqual(published_data['change_rate'], self.service.change_rate)

            # Verify response
            self.assertEqual(status_code, 200)

    @patch('requests.post')
    def test_no_emergency_brake_when_safe(self, mock_post):
        """Test 3: No emergency brake when distance is safe"""
        # Arrange
        self.service.last_dst_front = 25.0
        self.service.last_time = datetime.now(timezone.utc)

        # Test data with safe distance
        test_data = {
            "vin": "TEST001",
            "dst_front": 20.0,  # Greater than 10.0 - safe distance
            "speed": 30.0,
            "time": datetime.now(timezone.utc).isoformat(timespec="microseconds")
        }

        # Mock Flask request
        with patch('flask.request') as mock_request:
            mock_request.get_json.return_value = test_data

            # Act
            response, status_code = self.service.receive_data()

            # Assert
            # Emergency brake should NOT be triggered
            mock_post.assert_not_called()

            # Only RabbitMQ publish should happen
            self.mock_channel.basic_publish.assert_called_once()

            # Verify response
            self.assertEqual(status_code, 200)

    def test_change_rate_calculation(self):
        """Test 4: Verify change rate calculation logic"""
        # Arrange
        initial_time = datetime.now(timezone.utc)
        self.service.last_dst_front = 30.0
        self.service.last_time = initial_time

        # Test data
        test_data = {
            "vin": "TEST001",
            "dst_front": 25.0,  # Distance decreased by 5 meters
            "speed": 40.0,
            "time": (initial_time.timestamp() + 2.0)  # 2 seconds later
        }

        # Convert timestamp back to ISO format
        test_data["time"] = datetime.fromtimestamp(test_data["time"], timezone.utc).isoformat(timespec="microseconds")

        # Mock Flask request
        with patch('flask.request') as mock_request:
            mock_request.get_json.return_value = test_data

            # Act
            response, status_code = self.service.receive_data()

            # Assert
            # change_rate = (30.0 - 25.0) / 2.0 = 2.5 m/s
            self.assertAlmostEqual(self.service.change_rate, 2.5, places=1)
            self.assertEqual(self.service.last_dst_front, 25.0)

    @patch('requests.post')
    def test_rabbitmq_failure_handling(self, mock_post):
        """Test 5: Handle RabbitMQ connection failure gracefully"""
        # Arrange
        from pika.exceptions import AMQPConnectionError

        # Make channel.basic_publish raise an exception
        self.mock_channel.basic_publish.side_effect = AMQPConnectionError("Connection lost")

        test_data = {
            "vin": "TEST001",
            "dst_front": 15.0,
            "speed": 50.0,
            "time": datetime.now(timezone.utc).isoformat(timespec="microseconds")
        }

        # Mock Flask request
        with patch('flask.request') as mock_request:
            mock_request.get_json.return_value = test_data

            # Act
            response, status_code = self.service.receive_data()

            # Assert
            # Should still return success even if RabbitMQ fails
            self.assertEqual(status_code, 200)

            # Verify retry queue was used
            self.service.retry_queue.put.assert_called_once()

            # Verify connection_dead was notified
            self.service.connection_dead.notify_all.assert_called_once()

    @patch('requests.post')
    def test_http_request_failure_handling(self, mock_post):
        """Test 6: Handle HTTP request failure for emergency brake"""
        # Arrange
        os.environ['SERVICE_DEPLOYMENT_LOCATION'] = 'vehicle'
        self.service.last_dst_front = 15.0

        # Mock failed HTTP response
        mock_post.side_effect = Exception("Connection refused")

        # Test data that should trigger emergency brake
        test_data = {
            "vin": "TEST001",
            "dst_front": 5.0,
            "speed": 60.0,
            "time": datetime.now(timezone.utc).isoformat(timespec="microseconds")
        }

        # Mock Flask request
        with patch('flask.request') as mock_request:
            mock_request.get_json.return_value = test_data

            # Act
            response, status_code = self.service.receive_data()

            # Assert
            # Should log error but still process RabbitMQ message
            self.service.logger.error.assert_called()
            self.mock_channel.basic_publish.assert_called()
            self.assertEqual(status_code, 200)


if __name__ == '__main__':
    unittest.main()