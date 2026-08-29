"""
Supplementary OCR using EasyOCR (pure Python, no external executables).

Runs on the same sampled frames used for vision analysis (not every raw
video frame). OCR failures on individual frames are skipped, never fatal.

EasyOCR is a pure-Python library that doesn't require system executables
like Tesseract, making it compatible with environments with security policies
that block executable downloads.
"""
import logging
from typing import List

from app.schemas.models import FrameRecord, OcrResult

logger = logging.getLogger(__name__)

_reader = None
_initialized = False


def _ensure_reader_initialized():
    """Initialize EasyOCR reader on first use (lazy loading)."""
    global _reader, _initialized
    if _initialized:
        return _reader

    try:
        import easyocr
        # Initialize reader for English (can add more languages if needed)
        # gpu=False for CPU-only environments
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        _initialized = True
        logger.info("EasyOCR reader initialized successfully")
        return _reader
    except ImportError as exc:
        logger.warning("easyocr not available, skipping OCR: %s", exc)
        _initialized = True
        return None
    except Exception as exc:
        logger.warning("Failed to initialize EasyOCR: %s", exc)
        _initialized = True
        return None


def run_ocr_on_frames(frames: List[FrameRecord]) -> List[OcrResult]:
    """
    Run OCR on video frames using EasyOCR.

    Returns a list of OCR results with text and confidence scores.
    Failures on individual frames are skipped (non-fatal).
    """
    reader = _ensure_reader_initialized()
    if reader is None:
        logger.info("OCR not available, skipping")
        return []

    results: List[OcrResult] = []
    for frame in frames:
        try:
            # EasyOCR returns list of [bbox, text, confidence] tuples
            ocr_results = reader.readtext(str(frame.frame_path))

            if not ocr_results:
                continue

            # Extract text and confidences
            texts = []
            confidences = []
            for (bbox, text, confidence) in ocr_results:
                text = (text or "").strip()
                if text:  # Only include non-empty text
                    texts.append(text)
                    confidences.append(float(confidence))

            if not texts:
                continue

            # Combine text and calculate average confidence
            joined_text = " ".join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Normalize confidence to 0-1 range (EasyOCR already returns 0-1)
            avg_confidence = round(max(0.0, min(1.0, avg_confidence)), 2)

            results.append(
                OcrResult(
                    timestamp=frame.timestamp,
                    text=joined_text,
                    confidence=avg_confidence,
                )
            )
        except Exception as exc:  # noqa: BLE001 - one bad frame must not stop OCR
            logger.warning("OCR failed on frame %s: %s", frame.frame_number, exc)
            continue

    return results
