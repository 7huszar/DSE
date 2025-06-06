import unittest
import json
import time
from unittest.mock import Mock, patch, MagicMock

import sys
sys.modules['pika'] = MagicMock()

from src.backend.distance_monitor.BackendDistanceMonitor import calculate_change_rate, check_emergency_conditions, vehicle_dm_callback

class TestBackendDistanceMonitor(unittest.TestCase):
    """Test cases for the Backend Distance Monitor service"""

    def test_calculate_change_rate(self):
        """Test distance change rate calculation"""
        # Test normal calculation
        rate = calculate_change_rate(current_distance=20.0, last_distance=25.0, time_diff=1.0)
        self.assertEqual(rate, -5.0)  # Distance decreased by 5m in 1s

        # Test no previous distance
        rate = calculate_change_rate(current_distance=20.0, last_distance=None, time_diff=1.0)
        self.assertEqual(rate, 0)

        # Test zero time difference
        rate = calculate_change_rate(current_distance=20.0, last_distance=25.0, time_diff=0)
        self.assertEqual(rate, 0)

    def test_check_emergency_conditions(self):
        """Test emergency condition checking"""
        # Test condition 1: distance < 20m and rate < -3m/s (decreasing)
        self.assertTrue(check_emergency_conditions(15.0, -4.0))

        # Test condition 2: distance < 40m and rate < -5m/s (decreasing)
        self.assertTrue(check_emergency_conditions(35.0, -6.0))

        # Test safe condition
        self.assertFalse(check_emergency_conditions(50.0, -2.0))

        # Test edge cases
        self.assertFalse(check_emergency_conditions(20.0, -3.0))  # Exactly at threshold
        self.assertFalse(check_emergency_conditions(15.0, -2.0))  # Distance critical but rate safe

if __name__ == '__main__':
    unittest.main()