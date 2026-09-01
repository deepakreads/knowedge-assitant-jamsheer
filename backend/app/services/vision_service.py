import logging
import time
import base64
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from pathlib import Path

from app.config import MAX_CONCURRENT_VISION_WORKERS, VISION_MODEL
from app.schemas.models import FrameRecord, VisionObservation
from app.services import ai_service

logger = logging.getLogger(__name__)

VISION_SYSTEM_PROMPT = (
    "You are an industrial computer vision analyst evaluating a manufacturing process video. "
    "Describe physical operator actions when a human is present, or describe internal mechanical "
    "operations (screw rotation, melt flow, mold closing) when looking at machine cutaways or 3D diagrams. "
    "Completely ignore background surroundings like brick walls, pallets, or furniture."
)

VISION_USER_PROMPT = """Analyze this video frame from a manufacturing training video.

If an operator is visible, describe their exact physical hand or body action.
If NO operator is visible (e.g., 3D machine cutaway, internal component diagram, polymer flow), describe the exact mechanical process shown (e.g., 'plasticizing screw rotating inside heated barrel', 'molten polymer discharging from injection nozzle into mold cavity').

Return ONLY a JSON object with this exact shape:
{
  "actions": ["specific physical action OR mechanical process observed"],
  "objects": ["active machine parts, mold components, or resin visible"],
  "tools": ["hand tools or machine instruments in active use"],
  "text": ["visible screen values, gauge readings, or labels"],
  "measurements": ["display readings"],
  "safety_observations": ["PPE or operational hazards"],
  "quality_observations": ["defect status or proper melt flow"],
  "confidence": 0.95
}

Rules:
- NEVER return generic strings like 'Activity performed by operator'.
- Name the specific machine part or resin state shown in the frame.
"""


def _process_single_frame(frame: FrameRecord) -> Optional[VisionObservation]:
    max_retries = 4
    base_delay = 2.0  # Base delay in seconds for exponential backoff

    for attempt in range(max_retries):
        try:
            raw_response = ai_service.generate(
                model=VISION_MODEL,
                prompt=VISION_USER_PROMPT,
                images=[frame.frame_path],
                system=VISION_SYSTEM_PROMPT,
                format_json=True,
                temperature=0.1,
                max_tokens=300,
            )
            parsed = ai_service.extract_json(raw_response)
            if not isinstance(parsed, dict):
                return None

            return VisionObservation(
                timestamp=frame.timestamp,
                frame_path=frame.frame_path,
                actions=[str(a) for a in parsed.get("actions", []) if str(a).strip()],
                objects=[str(o) for o in parsed.get("objects", []) if str(o).strip()],
                tools=[str(t) for t in parsed.get("tools", []) if str(t).strip()],
                text=[str(tx) for tx in parsed.get("text", []) if str(tx).strip()],
                measurements=[str(m) for m in parsed.get("measurements", []) if str(m).strip()],
                safety_observations=[str(s) for s in parsed.get("safety_observations", []) if str(s).strip()],
                quality_observations=[str(q) for q in parsed.get("quality_observations", []) if str(q).strip()],
                confidence=max(0.0, min(1.0, float(parsed.get("confidence") or 0.7))),
            )

        except Exception as exc:
            error_msg = str(exc).lower()
            
            # Check for Rate Limit (429) or transient errors
            if "429" in error_msg or "too many requests" in error_msg:
                wait_time = base_delay * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s, 16s
                logger.warning(
                    "Rate limited (429) at t=%.1fs. Retrying in %.1fs (Attempt %d/%d)...",
                    frame.timestamp, wait_time, attempt + 1, max_retries
                )
                time.sleep(wait_time)
            else:
                # Non-429 error, log and fail immediately
                logger.warning("Vision analysis failed for frame at t=%.1fs: %s", frame.timestamp, exc)
                return None

    logger.error("Max retries exceeded for frame at t=%.1fs due to rate limiting.", frame.timestamp)
    return None


def analyze_frames(frames: List[FrameRecord]) -> List[VisionObservation]:
    if not frames:
        return []

    logger.info("Analyzing %d frames with %d concurrent workers...", len(frames), MAX_CONCURRENT_VISION_WORKERS)
    results: List[Optional[VisionObservation]] = [None] * len(frames)

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_VISION_WORKERS) as executor:
        future_to_index = {
            executor.submit(_process_single_frame, frame): idx 
            for idx, frame in enumerate(frames)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            results[idx] = future.result()

    valid_observations = [obs for obs in results if obs is not None]
    logger.info("Vision analysis complete: %d/%d valid observations.", len(valid_observations), len(frames))
    return valid_observations


async def analyze_frame_with_prompt(frame_base64: str, custom_prompt: str) -> str:
    """
    Analyze a base64-encoded frame with a custom prompt for real-time monitoring.

    Args:
        frame_base64: Base64-encoded JPEG frame data
        custom_prompt: Custom prompt for analysis (e.g., SOP compliance check)

    Returns:
        Analysis text from the vision model
    """
    try:
        # Decode base64 to temporary file
        frame_data = base64.b64decode(frame_base64)

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(frame_data)
            tmp_path = tmp.name

        try:
            # Call AI service with the custom prompt
            response = ai_service.generate(
                model=VISION_MODEL,
                prompt=custom_prompt,
                images=[tmp_path],
                system=VISION_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=500,
            )

            logger.info("Frame analysis complete")
            return response

        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Frame analysis failed: {e}")
        raise