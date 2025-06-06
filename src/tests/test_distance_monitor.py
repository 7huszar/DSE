import unittest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from collections import defaultdict

# Mock the modules before importing
import sys
sys.modules['pika'] = MagicMock()

class TestBackendDistanceMonitor(unittest.TestCase):
    """Test cases for the Backend Distance Monitor service"""

    @patch('src.backend.distance_monitor.BackendDistanceMonitor.get_rabbitmq_connection')
    def test_calculate_change_rate(self, mock_connection):
        """Test distance change rate calculation"""
        from src.backend.distance_monitor.BackendDistanceMonitor import calculate_change_rate

        # Test normal calculation
        rate = calculate_change_rate(20.0, 25.0, 1.0)
        self.assertEqual(rate, -5.0)  # Distance decreased by 5m in 1s

        # Test no previous distance
        rate = calculate_change_rate(20.0, None, 1.0)
        self.assertEqual(rate, 0)

        # Test zero time difference
        rate = calculate_change_rate(20.0, 25.0, 0)
        self.assertEqual(rate, 0)

    @patch('src.backend.distance_monitor.BackendDistanceMonitor.get_rabbitmq_connection')
    def test_check_emergency_conditions(self, mock_connection):
        """Test emergency condition checking"""
        from src.backend.distance_monitor.BackendDistanceMonitor import check_emergency_conditions

        # Test condition 1: distance < 20m and rate > 3m/s
        self.assertTrue(check_emergency_conditions(15.0, -4.0))

        # Test condition 2: distance < 40m and rate > 5m/s
        self.assertTrue(check_emergency_conditions(35.0, -6.0))

        # Test safe condition
        self.assertFalse(check_emergency_conditions(50.0, -2.0))

        # Test edge cases
        self.assertFalse(check_emergency_conditions(20.0, -3.0))  # Exactly at threshold
        self.assertFalse(check_emergency_conditions(15.0, -2.0))  # Distance critical but rate safe

if __name__ == '__main__':
    unittest.main()