"""
Speech-to-text using local Whisper.

If the video has no audio track, or Whisper fails to load/run, this returns
an empty transcript rather than failing the whole job -- visual analysis can
still produce an SOP on its own.

Memory note: Whisper is forced onto CPU (WHISPER_DEVICE) so it never
competes with Ollama for the 8GB GPU. It is also *not* cached across jobs --
with only ~10GB of free RAM after Ollama/backend/frontend are running, an
indefinitely-cached model is a standing cost you pay even when nothing is
transcribing. It's loaded, used, and released within a single call instead;
the load itself is a few seconds for the "base" model, which is negligible
next to the vision/text model stages.
"""
import gc
import logging
from typing import List

from app.config import WHISPER_DEVICE, WHISPER_MODEL
from app.schemas.models import TranscriptSegment

logger = logging.getLogger(__name__)


def transcribe_audio(audio_path: str) -> List[TranscriptSegment]:
    """
    Transcribe an audio file with timestamps. Returns [] on any failure
    (missing audio, missing package, transcription error) so the caller can
    continue the pipeline without audio evidence.
    """
    if not audio_path:
        logger.info("No audio track available; skipping transcription.")
        return []

    try:
        import whisper  # openai-whisper
    except ImportError as exc:
        logger.warning(
            "The 'openai-whisper' package is not installed; continuing without audio: %s", exc
        )
        return []

    model = None
    try:
        logger.info("Loading Whisper model '%s' on %s...", WHISPER_MODEL, WHISPER_DEVICE)
        model = whisper.load_model(WHISPER_MODEL, device=WHISPER_DEVICE)
        result = model.transcribe(audio_path, verbose=False, fp16=False)
    except Exception as exc:  # noqa: BLE001 - transcription must never crash the job
        logger.warning("Whisper transcription failed, continuing without audio: %s", exc)
        return []
    finally:
        # Release the model's memory immediately rather than waiting for the
        # next GC cycle -- this is the one place in the pipeline holding a
        # large object in plain RAM instead of Ollama's VRAM, and RAM is the
        # tighter budget here.
        if model is not None:
            del model
        gc.collect()

    segments: List[TranscriptSegment] = []
    for seg in result.get("segments", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start=round(float(seg.get("start", 0.0)), 2),
                end=round(float(seg.get("end", 0.0)), 2),
                text=text,
            )
        )
    return segments
