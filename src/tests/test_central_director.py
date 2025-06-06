import sys
from unittest.mock import MagicMock

sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extras'] = MagicMock()

sys.modules['pika'] = MagicMock()
sys.modules['pika.exceptions'] = MagicMock()

import unittest
from unittest.mock import patch
from src.backend.central_director.CentralDirector import store_event, check_emergency_conditions

class TestCentralDirector(unittest.TestCase):
    """Test cases for the Central Director service"""

    @patch('src.backend.central_director.CentralDirector.get_db_connection')
    def test_store_event_to_db(self, mock_get_db_connection):
        """Test storing events to database"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_conn

        store_event("TEST001", "triggered", "DM", {"distance": 15.0})

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        self.assertIn("INSERT INTO emergency_events", call_args[0][0])
        self.assertEqual(call_args[0][1][0], "TEST001")
        mock_conn.commit.assert_called_once()

    def test_check_emergency_conditions(self):
        """Test all emergency conditions"""
        reasons = check_emergency_conditions(vin="TEST001", dm_distance=15.0, change_rate=-4.0)
        self.assertIn("Condition 1", reasons[0])

        reasons = check_emergency_conditions(vin="TEST001", dm_distance=35.0, change_rate=-6.0)
        self.assertIn("Condition 2", reasons[0])

        reasons = check_emergency_conditions(vin="TEST001", dm_distance=50.0, change_rate=-1.0, lt_distance=25.0)
        self.assertIn("Condition 3", reasons[0])

        reasons = check_emergency_conditions(vin="TEST001", dm_distance=50.0, change_rate=-2.0, lt_distance=55.0)
        self.assertEqual(len(reasons), 0)

        reasons = check_emergency_conditions(vin="TEST001", dm_distance=20.0, change_rate=-3.0)
        self.assertEqual(len(reasons), 0)

if __name__ == '__main__':
    unittest.main()