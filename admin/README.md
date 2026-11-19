# Django administration

`backend/core/healthcare_intelligence/admin.py` registers the existing healthcare models with Django admin. This folder adds `/admin/healthcare/`, a staff-only operations dashboard with aggregate counts and a searchable list of recent report records.

The dashboard uses HTML templates and its own CSS/JavaScript under `frontend/`. It does not expose report text or analysis results. Sign in with a Django staff account at `/admin/` to open it.
