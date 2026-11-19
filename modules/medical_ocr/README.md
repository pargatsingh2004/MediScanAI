# Medical OCR module

`backend/services/ocr_service.py` accepts local paths or uploaded bytes, invokes the existing PDF/image extractor, and removes temporary files after processing. `data_science/text_quality.py` exposes a readability signal for extraction review; it does not make clinical claims.

The upload and report review interface remains in the root `frontend/` directory.
