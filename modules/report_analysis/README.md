# Report analysis module

`backend/services/analysis_service.py` exposes the existing extraction-to-insights pipeline. The data science package contains clinical text normalization, transparent specialty keyword features, classifier evaluation, training, and cached prediction. The application's normalized measurements and existing clinical safeguards remain authoritative.

Run model training from the repository root with `python -m modules.report_analysis.data_science.training.train_specialty_model`. Report upload and analysis screens remain in the root `frontend/` directory.
