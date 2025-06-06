import unittest
import json
from unittest.mock import Mock, patch, MagicMock

mock_psycopg2 = MagicMock()
mock_psycopg2.extras = MagicMock()

sys.modules['psycopg2'] = mock_psycopg2
sys.modules['pika'] = MagicMock()

from src.backend.central_director.CentralDirector import store_event, check_emergency_conditions

class TestCentralDirector(unittest.TestCase):
    """Test cases for the Central Director service"""

    # Patch den DB-Connect in dem Modul, wo er verwendet wird
    @patch('src.backend.central_director.CentralDirector.get_db_connection')
    def test_store_event_to_db(self, mock_get_db_connection):
        """Test storing events to database"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_conn

        # Test storing event
        store_event("TEST001", "triggered", "DM", {"distance": 15.0})

        # Verify INSERT was called
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        self.assertIn("INSERT INTO emergency_events", call_args[0][0])
        self.assertEqual(call_args[0][1][0], "TEST001") # Check VIN

        # Verify commit was called
        mock_conn.commit.assert_called_once()

    def test_check_emergency_conditions(self):
        """Test all emergency conditions"""
        # Test condition 1: distance < 20m and rate < -3m/s (decreasing)
        reasons = check_emergency_conditions("TEST001", dm_distance=15.0, change_rate=-4.0)
        self.assertIn("Condition 1", reasons[0])

        # Test condition 2: distance < 40m and rate < -5m/s (decreasing)
        reasons = check_emergency_conditions("TEST001", dm_distance=35.0, change_rate=-6.0)
        self.assertIn("Condition 2", reasons[0])

        # Test condition 3: Plausibility check |DM - LT| > 20m
        reasons = check_emergency_conditions("TEST001", dm_distance=50.0, change_rate=-1.0, lt_distance=25.0)
        self.assertIn("Condition 3", reasons[0])

        # Test safe condition
        reasons = check_emergency_conditions("TEST001", dm_distance=50.0, change_rate=-2.0, lt_distance=55.0)
        self.assertEqual(len(reasons), 0)

        # Test edge cases (should not trigger)
        reasons = check_emergency_conditions("TEST001", dm_distance=20.0, change_rate=-3.0)
        self.assertEqual(len(reasons), 0)

if __name__ == '__main__':
    unittest.main()