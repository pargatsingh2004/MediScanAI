# MediScan AI

MediScan AI uses Django for the Python backend and serves HTML, CSS, and browser JavaScript directly through Django. It includes report uploads and OCR, report history and analysis, a report-aware health assistant, comparisons, trends, reminders, doctor and hospital discovery, appointments, and navigation.

## Run locally

1. Create and activate a Python virtual environment:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r backend/requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure deployment values locally:
   ```powershell
   Copy-Item .env.example .env
   ```
4. Apply database migrations:
   ```powershell
   python run.py migrate
   ```
5. Load the bundled specialty categories:
   ```powershell
   python run.py seed_healthcare_data
   ```
   This loads specialty categories only. Hospital and doctor records from the old sample files are not treated as verified providers.
6. Start the complete application:
   ```powershell
   python run.py
   ```

The development server is available at `http://127.0.0.1:8000/`. Other Django management commands can also be run through `python run.py <command>`.

## Authentication

- Django's existing `User` model is the only account system.
- The single login page provides all modules through the same session.
- Registration and password reset use six-digit, 10-minute OTP codes.
- Verification OTP resend requests are rate-limited.
- Report, reminder, favorite, chat, and location records remain associated with the authenticated account.

## Database migration safety

Existing SQLite records are preserved. No migration resets or deletes existing tables. Migration `0006` keeps old sample hospital and doctor rows, but marks them unverified and removes unsupported ratings, emergency-service claims, and appointment availability.

Before changing an existing production database, create a backup:

```powershell
Copy-Item database/db.sqlite3 database/db.sqlite3.backup
```

Check migrations before applying:

```powershell
python run.py makemigrations --check --dry-run
python run.py migrate --plan
```

## Testing

```powershell
python run.py check
python run.py test tests --verbosity 1
```

The test suite covers report extraction, recommendations, navigation, API integration, OTP verification, favorites, reminders, profile updates, and CSV exports.

## Modular structure

Existing implementation files remain as compatibility routes and services. Module packages are under `modules/`:

- `authentication/`
- `chatbot/`
- `hospital_finder/`
- `doctor_finder/`
- `report_analysis/`
- `medical_ocr/`
- `health_trends/`
- `report_comparison/`
- `reminders/`
- `maps_navigation/`

Shared infrastructure is under `shared/`. Module notifications require the central notification preferences; they are never sent without user consent.

The module service entry points are documented in `modules/README.md` and each feature module's README. Their backend services are used by the existing Django routes; the shared HTML, CSS, and JavaScript remain under `frontend/`.

## Django administration

Create a staff account with `python run.py createsuperuser`, then sign in at `http://127.0.0.1:8000/admin/`. The staff-only project overview is at `http://127.0.0.1:8000/admin/healthcare/`.

## OCR and optional integrations

The report extractor supports text PDFs and JPG/PNG reports. Scanned PDFs use PyMuPDF and Tesseract OCR. Install Tesseract on the host and set `TESSERACT_CMD` if it is not on the system path.

Google Places and OpenAI integrations are optional. Local report analysis remains available without an OpenAI key. Google Maps keys and Gmail SMTP credentials belong only in `.env`, never in source code or frontend JavaScript.

## Provider directory

Only providers explicitly verified in the local directory are shown as MediScanAI-verified or can be used for appointment booking. Google Places and OpenStreetMap results are labeled as external listings and are not independently verified by MediScanAI. The specialty seed command does not create hospital or doctor records.
