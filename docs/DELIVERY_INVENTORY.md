# Delivery Inventory

## Preserved

- Existing SQLite database and migration history
- Django `User` authentication model and session configuration
- Existing landing, login, workspace, hospital, doctor, report, and navigation templates
- Existing CSS and JavaScript theme
- Existing hospital, doctor, specialty, report, finding, chat, reminder, appointment, and location models
- Existing API compatibility routes
- Specialty categories and the existing ML model
- Existing test suite
- Legacy sample hospital and doctor rows retained but marked unverified

## Added

- `run.py`
- `docs/MODULAR_ARCHITECTURE.md`
- `backend/authentication/`
- `shared/email/email_service.py`
- `modules/*/README.md`
- Module service APIs wired to report analysis, OCR, chat, doctor/hospital search, navigation, reminders, trends, comparisons, and account verification
- Specialty text preprocessing, keyword feature extraction, classifier evaluation, and safe model training utilities
- Staff-only operations dashboard under `admin/` with HTML, CSS, JavaScript, and a Django URL
- `backend/core/healthcare_intelligence/admin.py`
- OTP and notification preference models
- Saved hospital and doctor models
- Reminder type and email-consent fields
- Profile, favorites, notification, OTP, trends export, and comparison export APIs
- OTP and ownership-focused tests
- Provider verification defaults and a migration that deactivates unsupported sample details

## Modified

- `README.md`
- `.env.example`
- `backend/core/healthcare_intelligence/backend/models.py`
- `backend/core/healthcare_intelligence/backend/workspace_urls.py`
- `backend/core/healthcare_intelligence/backend/workspace_views.py`
- `tests/test_api_integration.py`
- `frontend/pages/healthcare_intelligence/email_confirm.txt`
- `frontend/pages/healthcare_intelligence/auth.html`
- `frontend/pages/healthcare_intelligence/workspace.html`
- `frontend/js/auth.js`
- `frontend/js/workspace.js`
- `backend/core/healthcare_intelligence/backend/services/hospital_finder.py`
- `backend/core/healthcare_intelligence/backend/services/doctor_recommender.py`
- `database/migrations/0006_unverify_seeded_directory.py`
