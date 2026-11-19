from django.test import TestCase
from backend.core.healthcare_intelligence.backend.services.hospital_finder import haversine_distance, HospitalFinder
from backend.core.healthcare_intelligence.backend.services.directions_service import DirectionsService


class NavigationServicesTestCase(TestCase):
    def test_haversine_distance(self):
        # Distance between Connaught Place (28.6304, 77.2177) and AIIMS Delhi (28.5672, 77.2100) is approx 7 km
        dist = haversine_distance(28.6304, 77.2177, 28.5672, 77.2100)
        self.assertGreater(dist, 5.0)
        self.assertLess(dist, 10.0)

    def test_navigation_url_generation(self):
        url = DirectionsService.get_navigation_url(28.5367, 77.2882, 28.6304, 77.2177, "driving")
        self.assertIn("https://www.google.com/maps/dir/?api=1", url)
        self.assertIn("destination=28.5367,77.2882", url)
        self.assertIn("travelmode=driving", url)

    def test_route_calculation_fallback(self):
        route = DirectionsService.calculate_route_summary(28.6304, 77.2177, 28.5672, 77.2100, "driving")
        self.assertIn("distance_text", route)
        self.assertIn("duration_text", route)
        self.assertIn("navigation_url", route)
