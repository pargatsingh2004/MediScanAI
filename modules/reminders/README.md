# Reminders module

`backend/services/reminder_service.py` validates 24-hour reminder times and selects due reminders. The existing reminder API and scheduled Django command use the central reminder models, Django session, and notification consent preferences. Browser alarms and styling remain in the root `frontend/` directory.
