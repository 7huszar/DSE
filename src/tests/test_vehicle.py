import unittest
import time
import math
from src.vehicle.data_mock.vehicle import Vehicle

class TestVehicleSample(unittest.TestCase):
    """Test cases for the Vehicle.sample() method"""

    def setUp(self):
        """Set up test vehicles"""
        self.vehicle1 = Vehicle(
            vin="TEST001",
            longitude=16.3738,
            latitude=48.2082,
            velocity=10.0,  # 10 m/s
            acceleration=0.0,
            direction=[1.0, 0.0]  # Moving east
        )

        self.vehicle2 = Vehicle(
            vin="TEST002",
            longitude=16.3738,
            latitude=48.2082,
            velocity=5.0,  # 5 m/s
            acceleration=0.0,
            direction=[0.0, 1.0]  # Moving north
        )

    def test_sample_position_update(self):
        """Test that sample() correctly updates vehicle position"""
        # Record initial position
        initial_lat = self.vehicle1.latitude
        initial_lon = self.vehicle1.longitude
        initial_time = self.vehicle1.internal_time

        # Wait a bit to ensure time difference
        time.sleep(0.1)

        # Call sample
        new_position = self.vehicle1.sample()

        # Check return value structure
        self.assertEqual(len(new_position), 3)
        self.assertIsInstance(new_position["lat"], float)  # latitude
        self.assertIsInstance(new_position["long"], float)  # longitude
        self.assertIsInstance(new_position["internal_time"], float)  # time

        # Check that position has changed (vehicle moving east)
        self.assertNotEqual(new_position["long"], initial_lon)
        self.assertEqual(new_position["lat"], self.vehicle1.latitude)

        # Since direction is [1, 0] (east), latitude should stay same
        self.assertAlmostEqual(initial_lat, new_position["lat"], places=5)

        # Longitude should increase (moving east)
        self.assertGreater(new_position["long"], initial_lon)

        # Time should have increased
        self.assertGreater(new_position["internal_time"], initial_time)

    def test_sample_distance_calculation(self):
        """Test that distance calculation is correct based on velocity and time"""
        # Record initial position
        initial_lat = self.vehicle2.latitude
        initial_lon = self.vehicle2.longitude

        # Set a known time difference
        time.sleep(1.0)  # 1 second

        # Call sample
        new_position = self.vehicle2.sample()

        # Vehicle 2 moves north at 5 m/s for ~1 second
        # Calculate expected latitude change
        # Using the formula from the code:
        # dy = direction[1] * distance = 1.0 * (5 m/s * 1s) = 5 meters
        # latitude change = (dy / earth_radius) * (180 / pi)
        expected_lat_change = (5.0 / self.vehicle2.earth_radius) * (180 / math.pi)

        # Check latitude increased (moving north)
        actual_lat_change = new_position["lat"] - initial_lat

        # Allow for some time measurement error
        self.assertAlmostEqual(actual_lat_change, expected_lat_change, places=6)

        # Longitude should stay the same (moving north only)
        self.assertAlmostEqual(new_position["long"], initial_lon, places=7)

class TestVehicleScenarios(unittest.TestCase):
    """Test vehicle behavior in different scenarios"""

    def test_stationary_vehicle(self):
        """Test that a stationary vehicle doesn't move"""
        stationary = Vehicle(
            vin="STATIONARY",
            longitude=16.3738,
            latitude=48.2082,
            velocity=0.0,  # Not moving
            direction=[1.0, 0.0]
        )

        initial_pos = [stationary.latitude, stationary.longitude]
        time.sleep(0.1)
        new_pos = stationary.sample()

        # Position should not change
        self.assertAlmostEqual(new_pos["lat"], initial_pos[0], places=10)
        self.assertAlmostEqual(new_pos["long"], initial_pos[1], places=10)

    def test_diagonal_movement(self):
        """Test vehicle moving diagonally"""
        diagonal = Vehicle(
            vin="DIAGONAL",
            longitude=16.3738,
            latitude=48.2082,
            velocity=10.0,
            direction=[0.707, 0.707]  # 45 degrees (normalized)
        )

        initial_lat = diagonal.latitude
        initial_lon = diagonal.longitude

        time.sleep(0.1)
        new_pos = diagonal.sample()

        # Both latitude and longitude should increase
        self.assertGreater(new_pos["lat"], initial_lat)
        self.assertGreater(new_pos["long"], initial_lon)

def run_tests():
    """Run all tests and return results"""
    # Create test suite
    suite = unittest.TestSuite()

    # Add all test cases
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestVehicleSample))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestVehicleScenarios))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()

if __name__ == '__main__':
    # Run tests
    success = run_tests()

    # Exit with appropriate code
    exit(0 if success else 1)