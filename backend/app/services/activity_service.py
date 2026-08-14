import gc
import logging
from typing import List

from app.config import SOP_MODEL
from app.schemas.models import (
    ActivityTimelineEntry,
    OcrResult,
    TranscriptSegment,
    VisionObservation,
)
from app.services import ai_service

logger = logging.getLogger(__name__)

ACTIVITY_SYSTEM_PROMPT = (
    "You are a manufacturing process analyst. Group frame-by-frame visual evidence, "
    "transcript audio, and OCR text into a consolidated chronological sequence of distinct "
    "operational phases. Merge repetitive consecutive frame observations into single continuous activities."
)

ACTIVITY_PROMPT_TEMPLATE = """Timestamped video evidence:

VISUAL OBSERVATIONS:
{visual_evidence}

SPEECH TRANSCRIPT:
{transcript}

OCR TEXT:
{ocr_text}

Consolidate adjacent duplicate observations into a logical sequence of distinct worker or machine activities (target 6 to 12 main phases).
Return ONLY a JSON object:

{{
  "activities": [
    {{
      "start_time": 0.0,
      "end_time": 15.0,
      "activity": "detailed description of physical or mechanical action performed",
      "visual_evidence": ["key visual observations"],
      "speech": "transcript snippet if applicable, or empty string",
      "ocr": ["relevant OCR strings"],
      "tools": ["tools used"],
      "materials": ["materials or components handled"],
      "confidence": 0.90
    }}
  ]
}}
"""


def _format_visual_evidence(observations: List[VisionObservation]) -> str:
    lines = []
    for obs in observations:
        parts = []
        if obs.actions:
            parts.append(f"actions={obs.actions}")
        if obs.objects:
            parts.append(f"objects={obs.objects}")
        if obs.tools:
            parts.append(f"tools={obs.tools}")
        if not parts:
            continue
        lines.append(f"[t={obs.timestamp}s] " + "; ".join(parts))
    return "\n".join(lines) if lines else "(no clear visual observations)"


def _format_transcript(segments: List[TranscriptSegment]) -> str:
    if not segments:
        return "(no speech detected)"
    return "\n".join(f"[{seg.start}s-{seg.end}s] {seg.text}" for seg in segments)


def _format_ocr(results: List[OcrResult]) -> str:
    if not results:
        return "(no OCR text detected)"
    return "\n".join(f"[t={r.timestamp}s] {r.text}" for r in results)


def _fallback_timeline_from_vision(
    observations: List[VisionObservation],
) -> List[ActivityTimelineEntry]:
    """Fallback method that merges adjacent duplicate frame observations into single timeline steps."""
    if not observations:
        return []

    grouped: List[dict] = []
    for obs in observations:
        act = obs.actions[0] if obs.actions else "Machine component operation or resin processing."
        if grouped and grouped[-1]["activity"].lower() == act.lower():
            grouped[-1]["end_time"] = obs.timestamp + 4.0
            grouped[-1]["materials"].extend(obs.objects)
            grouped[-1]["tools"].extend(obs.tools)
        else:
            grouped.append({
                "start_time": obs.timestamp,
                "end_time": obs.timestamp + 4.0,
                "activity": act,
                "materials": list(obs.objects),
                "tools": list(obs.tools),
                "confidence": obs.confidence,
                "frame": obs.frame_path,
            })

    entries: List[ActivityTimelineEntry] = []
    for i, item in enumerate(grouped):
        entries.append(
            ActivityTimelineEntry(
                step=i + 1,
                start_time=item["start_time"],
                end_time=item["end_time"],
                activity=item["activity"],
                visual_evidence=[item["activity"]],
                speech="",
                ocr=[],
                tools=list(set(item["tools"])),
                materials=list(set(item["materials"])),
                confidence=item["confidence"],
                frame_reference=item["frame"],
            )
        )
    return entries


def build_activity_timeline(
    vision_observations: List[VisionObservation],
    transcript: List[TranscriptSegment],
    ocr_results: List[OcrResult],
) -> List[ActivityTimelineEntry]:
    if not vision_observations:
        logger.warning("No vision observations available; cannot build timeline.")
        return []

    logger.info("Building activity timeline with %s model...", SOP_MODEL)

    prompt = ACTIVITY_PROMPT_TEMPLATE.format(
        visual_evidence=_format_visual_evidence(vision_observations),
        transcript=_format_transcript(transcript),
        ocr_text=_format_ocr(ocr_results),
    )

    try:
        raw = ai_service.generate(
            model=SOP_MODEL,
            prompt=prompt,
            system=ACTIVITY_SYSTEM_PROMPT,
            format_json=True,
            temperature=0.0,
            max_tokens=1800,
        )
        parsed = ai_service.extract_json(raw)

        raw_items = []
        if isinstance(parsed, dict):
            raw_items = parsed.get("activities") or []
        elif isinstance(parsed, list):
            raw_items = parsed

        if not raw_items:
            raise ValueError("Activity model did not return usable activities list")

        entries: List[ActivityTimelineEntry] = []
        for i, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            start_time = float(item.get("start_time", 0.0) or 0.0)
            end_time = float(item.get("end_time", start_time + 5.0) or (start_time + 5.0))
            frame_ref = _nearest_frame_reference(vision_observations, start_time)
            entries.append(
                ActivityTimelineEntry(
                    step=i + 1,
                    start_time=start_time,
                    end_time=max(start_time, end_time),
                    activity=str(item.get("activity", "") or "").strip() or "Machine component operation.",
                    visual_evidence=[str(v) for v in (item.get("visual_evidence") or []) if str(v).strip()],
                    speech=str(item.get("speech", "") or "").strip(),
                    ocr=[str(v) for v in (item.get("ocr") or []) if str(v).strip()],
                    tools=[str(v) for v in (item.get("tools") or []) if str(v).strip()],
                    materials=[str(v) for v in (item.get("materials") or []) if str(v).strip()],
                    confidence=max(0.0, min(1.0, float(item.get("confidence") or 0.85))),
                    frame_reference=frame_ref,
                )
            )
        if not entries:
            raise ValueError("Parsed activity array yielded no valid entries")

        logger.info("Successfully built activity timeline with %d steps.", len(entries))
        return entries

    except Exception as exc:
        logger.warning("Activity timeline LLM failed (%s); using merged frame fallback.", exc)
        return _fallback_timeline_from_vision(vision_observations)
    finally:
        gc.collect()


def _nearest_frame_reference(observations: List[VisionObservation], timestamp: float):
    if not observations:
        return None
    closest = min(observations, key=lambda o: abs(o.timestamp - timestamp))
    return closest.frame_path
