"""
Supplementary OCR using Tesseract.

Runs on the same sampled frames used for vision analysis (not every raw
video frame). OCR failures on individual frames are skipped, never fatal.
"""
import logging
from typing import List

from app.config import TESSERACT_CMD
from app.schemas.models import FrameRecord, OcrResult

logger = logging.getLogger(__name__)

_configured = False


def _ensure_configured():
    global _configured
    if _configured:
        return
    try:
        import pytesseract

        if TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    except ImportError:
        pass
    _configured = True


def run_ocr_on_frames(frames: List[FrameRecord]) -> List[OcrResult]:
    _ensure_configured()
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        logger.warning("pytesseract/Pillow not available, skipping OCR entirely: %s", exc)
        return []

    results: List[OcrResult] = []
    for frame in frames:
        try:
            with Image.open(frame.frame_path) as img:
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        except Exception as exc:  # noqa: BLE001 - one bad frame must not stop OCR
            logger.warning("OCR failed on frame %s: %s", frame.frame_number, exc)
            continue

        words = []
        confidences = []
        for text, conf in zip(data.get("text", []), data.get("conf", [])):
            text = (text or "").strip()
            if not text:
                continue
            try:
                conf_val = float(conf)
            except (TypeError, ValueError):
                conf_val = -1.0
            if conf_val < 0:
                continue
            words.append(text)
            confidences.append(conf_val)

        if not words:
            continue

        joined_text = " ".join(words)
        avg_confidence = (sum(confidences) / len(confidences)) / 100.0 if confidences else 0.0
        results.append(
            OcrResult(
                timestamp=frame.timestamp,
                text=joined_text,
                confidence=round(max(0.0, min(1.0, avg_confidence)), 2),
            )
        )
    return results
