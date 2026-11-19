# Maps navigation module

`backend/services/navigation_service.py` validates coordinates, asks the existing directions service for route details, and creates Google Maps URLs. If no route API key is configured, the existing geodesic estimate remains available. The root `frontend/` directory owns the map interface and theme.
