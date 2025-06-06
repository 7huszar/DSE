import sys
from unittest.mock import MagicMock


sys.modules['pika'] = MagicMock()
sys.modules['pika.exceptions'] = MagicMock()

import unittest
from src.backend.distance_monitor.BackendDistanceMonitor import calculate_change_rate, check_emergency_conditions

class TestBackendDistanceMonitor(unittest.TestCase):
    """Test cases for the Backend Distance Monitor service"""

    def test_calculate_change_rate(self):
        rate = calculate_change_rate(current_distance=20.0, last_distance=25.0, time_diff=1.0)
        self.assertEqual(rate, -5.0)
        rate = calculate_change_rate(current_distance=20.0, last_distance=None, time_diff=1.0)
        self.assertEqual(rate, 0)
        rate = calculate_change_rate(current_distance=20.0, last_distance=25.0, time_diff=0)
        self.assertEqual(rate, 0)

    def test_check_emergency_conditions(self):
        self.assertTrue(check_emergency_conditions(15.0, -4.0))
        self.assertTrue(check_emergency_conditions(35.0, -6.0))
        self.assertFalse(check_emergency_conditions(50.0, -2.0))
        self.assertFalse(check_emergency_conditions(20.0, -3.0))

if __name__ == '__main__':
    unittest.main()