# Health trends module

`backend/services/trends_service.py` builds a user's chronological metric series and export rows. It reads saved report findings only for the user supplied by the authenticated Django endpoint. `data_science/trend_statistics.py` contains reusable last-value calculations.

The existing workspace charts and styles stay in the root `frontend/` directory.
