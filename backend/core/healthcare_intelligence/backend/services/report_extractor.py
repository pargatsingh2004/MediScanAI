import os
import re
import hashlib
import logging

logger = logging.getLogger(__name__)

# Prefer PyMuPDF's current import name; retain compatibility with older releases.
try:
    import pymupdf as fitz
    HAS_PYMUPDF = True
except Exception as pymupdf_error:
    try:
        import fitz  # Older PyMuPDF alias
        HAS_PYMUPDF = True
    except Exception as exc:
        logger.warning("PyMuPDF is unavailable: %s; legacy import failed: %s", pymupdf_error, exc)
        fitz = None
        HAS_PYMUPDF = False

# Fallback to pypdf
try:
    import pypdf
    HAS_PYPDF = True
except Exception as exc:
    logger.warning("pypdf is unavailable: %s", exc)
    pypdf = None
    HAS_PYPDF = False

# Tesseract is optional. Load it only when OCR is requested so an unavailable
# optional dependency cannot prevent Django commands such as migrate from starting.
pytesseract = None
Image = None
HAS_TESSERACT = None


def _load_tesseract():
    global pytesseract, Image, HAS_TESSERACT
    if HAS_TESSERACT is not None:
        return HAS_TESSERACT
    try:
        import pytesseract as pytesseract_module
        from PIL import Image as image_module
        pytesseract = pytesseract_module
        Image = image_module
        HAS_TESSERACT = True
    except Exception as exc:
        logger.warning("Optional Tesseract OCR dependencies are unavailable: %s", exc)
        HAS_TESSERACT = False
    return HAS_TESSERACT

# Try importing cv2 (OpenCV)
try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except Exception as exc:
    logger.warning("Optional OpenCV preprocessing is unavailable: %s", exc)
    cv2 = None
    np = None
    HAS_OPENCV = False


class ReportExtractor:
    """Extracts, cleans, and structures text from PDF documents and medical images."""

    @staticmethod
    def compute_sha256(file_path_or_bytes) -> str:
        """Compute SHA-256 hash for document authenticity."""
        hasher = hashlib.sha256()
        if isinstance(file_path_or_bytes, (bytes, bytearray)):
            hasher.update(file_path_or_bytes)
        elif hasattr(file_path_or_bytes, "read"):
            pos = file_path_or_bytes.tell() if hasattr(file_path_or_bytes, "tell") else 0
            for chunk in iter(lambda: file_path_or_bytes.read(65536), b""):
                hasher.update(chunk)
            if hasattr(file_path_or_bytes, "seek"):
                file_path_or_bytes.seek(pos)
        elif os.path.exists(file_path_or_bytes):
            with open(file_path_or_bytes, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def extract_from_pdf(cls, file_path: str) -> dict:
        """Extract text from a PDF file using PyMuPDF or pypdf."""
        raw_text = ""
        engine = "none"

        # Attempt 1: PyMuPDF (fitz)
        if HAS_PYMUPDF:
            try:
                doc = fitz.open(file_path)
                pages_text = []
                for page in doc:
                    pages_text.append(page.get_text() or "")
                doc.close()
                raw_text = "\n".join(pages_text).strip()
                if raw_text:
                    engine = "PyMuPDF"
            except Exception as e:
                logger.warning(f"PyMuPDF extraction failed: {e}")

        # Attempt 2: pypdf fallback
        if not raw_text and HAS_PYPDF:
            try:
                reader = pypdf.PdfReader(file_path)
                pages_text = []
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        pages_text.append(extracted)
                raw_text = "\n".join(pages_text).strip()
                if raw_text:
                    engine = "pypdf"
            except Exception as e:
                logger.warning(f"pypdf extraction failed: {e}")

        # Attempt 3: Text decoding fallback for mock/synthetic test documents
        if not raw_text:
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                if not content.startswith(b"%PDF"):
                    decoded = content.decode("utf-8", errors="ignore").strip()
                    if decoded:
                        raw_text = decoded
                        engine = "text_fallback"
            except Exception:
                pass

        # Scanned PDFs need an OCR pass after the text-layer extractors have failed.
        if not raw_text and HAS_PYMUPDF and _load_tesseract():
            try:
                tess_cmd = os.getenv("TESSERACT_CMD", "").strip()
                if tess_cmd:
                    pytesseract.pytesseract.tesseract_cmd = tess_cmd
                doc = fitz.open(file_path)
                ocr_pages = []
                for page in doc:
                    pixmap = page.get_pixmap(dpi=220, alpha=False)
                    mode = "RGB" if pixmap.n < 4 else "RGBA"
                    image = Image.frombytes(mode, [pixmap.width, pixmap.height], pixmap.samples)
                    page_text = pytesseract.image_to_string(image, lang="eng")
                    if page_text.strip():
                        ocr_pages.append(page_text)
                doc.close()
                raw_text = "\n".join(ocr_pages).strip()
                if raw_text:
                    engine = "PyMuPDF+Tesseract"
            except Exception as e:
                logger.warning(f"Scanned PDF OCR failed: {e}")

        cleaned_text = cls.clean_text(raw_text)
        return {
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "engine": engine,
            "success": bool(cleaned_text),
        }

    @classmethod
    def extract_from_image(cls, file_path: str) -> dict:
        """Extract text from an image using OpenCV preprocessing and Tesseract OCR."""
        raw_text = ""
        engine = "none"

        if _load_tesseract():
            try:
                tess_cmd = os.getenv("TESSERACT_CMD", "").strip()
                if tess_cmd:
                    pytesseract.pytesseract.tesseract_cmd = tess_cmd
                if HAS_OPENCV:
                    img = cv2.imread(file_path)
                    if img is not None:
                        # Grayscale conversion
                        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                        # Denoise
                        denoised = cv2.fastNlMeansDenoising(gray, h=10)
                        # Adaptive thresholding
                        thresh = cv2.adaptiveThreshold(
                            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                        )
                        pil_img = Image.fromarray(thresh)
                    else:
                        pil_img = Image.open(file_path)
                else:
                    pil_img = Image.open(file_path)

                raw_text = pytesseract.image_to_string(pil_img, lang="eng")
                engine = "Tesseract+OpenCV" if HAS_OPENCV else "Tesseract"
            except Exception as e:
                logger.warning(f"OCR extraction failed: {e}")

        cleaned_text = cls.clean_text(raw_text)
        return {
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "engine": engine,
            "success": bool(cleaned_text),
        }

    @classmethod
    def extract(cls, file_path: str, mime_type: str = "") -> dict:
        """Universal document extraction router."""
        ext = os.path.splitext(file_path)[1].lower()
        sha256 = cls.compute_sha256(file_path)

        if ext == ".pdf" or "pdf" in mime_type.lower():
            result = cls.extract_from_pdf(file_path)
            file_type = "pdf"
        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"] or "image" in mime_type.lower():
            result = cls.extract_from_image(file_path)
            file_type = "image"
        else:
            # Try PDF first then image
            result = cls.extract_from_pdf(file_path)
            if not result.get("success"):
                result = cls.extract_from_image(file_path)
            file_type = "unknown"

        result["sha256"] = sha256
        result["file_type"] = file_type
        return result

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize extracted medical report text."""
        if not text:
            return ""
        # Remove non-printable control characters
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
        # Normalize multiple spaces and non-breaking spaces
        text = text.replace("\u00a0", " ").replace("\ufeff", "")
        # Consolidate multiple empty lines
        lines = [line.strip() for line in text.splitlines()]
        cleaned_lines = []
        for line in lines:
            if line:
                cleaned_lines.append(re.sub(r"[ \t]+", " ", line))
        return "\n".join(cleaned_lines)
