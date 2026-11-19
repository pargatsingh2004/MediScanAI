# Report comparison module

`backend/services/comparison_service.py` compares numeric findings across an ordered report set, handles unit mismatches, and yields CSV export rows. The endpoint scopes reports to the signed-in user. `data_science/metrics.py` exposes unit-aware delta calculations.

The existing comparison interface remains in the root `frontend/` directory.
