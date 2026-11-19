# MediScanAI Modular Architecture

## Existing compatibility

The project retains its existing Django application, SQLite database, user model, migration history, templates, static assets, report records, and URL endpoints. `workspace_views.py` remains a compatibility layer while module boundaries and shared services are introduced incrementally.

## Module ownership

| Module | Existing implementation | Added boundary |
|---|---|---|
| Authentication | Django session auth and workspace endpoints | `modules/authentication/backend/services/` plus `backend/authentication/` |
| Shared email | Direct Django mail calls | `shared/email/` |
| Chatbot | Workspace report chat | `modules/chatbot/backend/services/` |
| Hospital finder | Hospital views, models, and services | `modules/hospital_finder/backend/services/` |
| Doctor finder | Doctor views, recommendations, appointments | `modules/doctor_finder/backend/services/` |
| Report analysis | Workspace extraction and analysis | `modules/report_analysis/backend/services/` and `data_science/` |
| Medical OCR | `ReportExtractor` service | `modules/medical_ocr/backend/services/` |
| Health trends | Trends API and workspace charts | `modules/health_trends/backend/services/` |
| Report comparison | Comparison API and workspace UI | `modules/report_comparison/backend/services/` |
| Reminders | Reminder API and scheduled email command | `modules/reminders/backend/services/` |
| Maps navigation | Directions and Google Maps integration | `modules/maps_navigation/backend/services/` |

## Main entry point

`run.py` loads Django, defaults to `127.0.0.1:8000`, and runs the existing single-server application. Module servers are not required.

The root `frontend/` directory remains the shared source for the product's HTML, CSS, and JavaScript. Module services feed those existing screens and preserve their routes and visual theme. The project operations page is available to staff at `/admin/healthcare/`.

## Database preservation

The central `django.contrib.auth.User` model and all existing `healthcare_intelligence` models remain in use. Migrations add OTP, notification preference, saved-item, and reminder fields. Migration `0006` preserves legacy sample provider rows but marks them unverified and clears unsupported provider claims.

## Authentication and authorization

Every protected report, chat, reminder, favorite, trend, comparison, and profile endpoint derives the current user from the central Django session. Report and reminder objects are queried by `user=request.user`; no module creates a separate login or user table.

## Email

Gmail SMTP can be configured through environment variables. OTP and password reset mail use the configured Django backend. Optional module mail must respect `NotificationPreference` and the module-specific consent setting.

## Administration

The existing healthcare models stay registered through `backend/core/healthcare_intelligence/admin.py`. The separate `admin/` project package supplies a staff-only overview, recent report status table, and filter control. Both the dashboard template directory and its static assets are registered in Django settings.
