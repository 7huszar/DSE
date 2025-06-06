import unittest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Mock modules
sys.modules['psycopg2'] = MagicMock()
sys.modules['pika'] = MagicMock()
sys.modules['requests'] = MagicMock()

class TestCentralDirector(unittest.TestCase):
    """Test cases for the Central Director service"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_channel = Mock()
        self.mock_connection = Mock()
        self.mock_db_conn = Mock()
        self.mock_cursor = Mock()
        self.mock_db_conn.cursor.return_value = self.mock_cursor

    @patch('src.vehicle.central_director.CentralDirector.db_conn')
    def test_store_event_to_db(self, mock_db):
        """Test storing events to database"""
        from src.backend.central_director.CentralDirector import store_event_to_db

        mock_db.cursor.return_value = self.mock_cursor

        # Test storing event
        store_event_to_db("TEST001", "triggered", "DM", {"distance": 15.0})

        # Verify INSERT was called
        self.mock_cursor.execute.assert_called()
        call_args = self.mock_cursor.execute.call_args
        self.assertIn("INSERT INTO emergency_events", call_args[0][0])

        # Verify commit was called
        mock_db.commit.assert_called()

    def test_check_emergency_conditions_case1(self):
        """Test emergency condition 1: distance < 20m and rate > 3m/s"""
        from src.backend.central_director.CentralDirector import check_emergency_conditions

        result = check_emergency_conditions("TEST001", 15.0, -4.0, 'front')
        self.assertTrue(result)

        # Test back distance (should not trigger)
        result = check_emergency_conditions("TEST001", 15.0, -4.0, 'back')
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()