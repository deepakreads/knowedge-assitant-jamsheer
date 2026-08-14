import gc
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from app.config import SOP_MODEL, SOPS_DIR
from app.schemas.models import ActivityTimelineEntry, Sop, SopStep
from app.services import ai_service
from app.services import elasticsearch_service

logger = logging.getLogger(__name__)

NOT_SPECIFIED = "Not specified in the source video."

SOP_SYSTEM_PROMPT = (
    "You are an industrial technical writer drafting a Standard Operating Procedure (SOP). "
    "Convert chronological timeline activities into active, imperative operational instructions "
    "(e.g., 'Inspect hopper', 'Verify temperature', 'Engage hydraulic screw')."
)

SOP_PROMPT_TEMPLATE = """Chronological activity timeline extracted from training video:

{timeline_json}

Draft a complete, detailed manufacturing SOP.
Return ONLY a valid JSON object with this exact schema:

{{
  "title": "precise technical procedure title",
  "purpose": "2-3 detailed sentences explaining the operational goal",
  "scope": "2-3 sentences specifying machine types and operational context",
  "required_tools": ["deduplicated list of tools and instruments used"],
  "required_materials": ["deduplicated list of active resins, parts, and machine components"],
  "safety": ["general safety precautions, PPE requirements, or operational hazard warnings"],
  "steps": [
    {{
      "step_number": 1,
      "title": "imperative step title naming precise action and component",
      "description": "3-4 detailed sentences explaining how to execute or verify this step",
      "tools": ["tools used in this step"],
      "materials": ["components manipulated in this step"],
      "safety_notes": ["step-specific safety or thermal hazard cautions"],
      "quality_check": "specific verification criteria or quality rule"
    }}
  ],
  "quality_checks": ["overall quality control checks upon job completion"],
  "estimated_duration": "calculated duration string"
}}

Rules:
- Generate EXACTLY one step per activity timeline entry in identical chronological order.
- Expand brief visual evidence into actionable technical instructions.
"""


def _timeline_to_prompt_json(timeline: List[ActivityTimelineEntry]) -> str:
    import json
    return json.dumps([entry.model_dump() for entry in timeline], indent=2)


def generate_sop(
    job_id: str,
    video_filename: str,
    timeline: List[ActivityTimelineEntry],
    title_hint: Optional[str] = None,
) -> Sop:
    if not timeline:
        raise ValueError("Cannot generate an SOP from an empty activity timeline.")

    logger.info("Generating detailed SOP for job %s using %s...", job_id, SOP_MODEL)

    prompt = SOP_PROMPT_TEMPLATE.format(
        timeline_json=_timeline_to_prompt_json(timeline),
    )

    steps: List[SopStep] = []
    parsed = None

    try:
        raw = ai_service.generate(
            model=SOP_MODEL,
            prompt=prompt,
            system=SOP_SYSTEM_PROMPT,
            format_json=True,
            temperature=0.0,
            max_tokens=3072,
        )
        parsed = ai_service.extract_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError("SOP model did not return a valid JSON object")
    except Exception as exc:
        logger.warning("Detailed SOP generation via LLM failed (%s); using timeline fallback.", exc)
        parsed = None

    clean_filename_title = (
        video_filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
        if video_filename else "Manufacturing Standard Operating Procedure"
    )

    if parsed:
        raw_steps = parsed.get("steps") or []
        for i, entry in enumerate(timeline):
            raw_step = raw_steps[i] if i < len(raw_steps) and isinstance(raw_steps[i], dict) else {}

            raw_tools = raw_step.get("tools") if raw_step.get("tools") is not None else entry.tools
            raw_mats = raw_step.get("materials") if raw_step.get("materials") is not None else entry.materials
            raw_safety = raw_step.get("safety_notes") or []

            steps.append(
                SopStep(
                    step_number=i + 1,
                    title=str(raw_step.get("title") or entry.activity or NOT_SPECIFIED),
                    description=str(raw_step.get("description") or entry.activity or NOT_SPECIFIED),
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    tools=[str(t) for t in (raw_tools or []) if str(t).strip()],
                    materials=[str(m) for m in (raw_mats or []) if str(m).strip()],
                    safety_notes=[str(s) for s in (raw_safety or []) if str(s).strip()],
                    quality_check=raw_step.get("quality_check") or None,
                    visual_reference=Path(entry.frame_reference).name if entry.frame_reference else None,
                    confidence=entry.confidence,
                )
            )
        title = str(parsed.get("title") or title_hint or clean_filename_title)
        purpose = str(parsed.get("purpose") or NOT_SPECIFIED)
        scope = str(parsed.get("scope") or NOT_SPECIFIED)
        required_tools = _dedupe([str(t) for t in (parsed.get("required_tools") or []) if str(t).strip()])
        required_materials = _dedupe([str(m) for m in (parsed.get("required_materials") or []) if str(m).strip()])
        safety = [str(s) for s in (parsed.get("safety") or []) if str(s).strip()]
        quality_checks = [str(q) for q in (parsed.get("quality_checks") or []) if str(q).strip()]
        estimated_duration = str(parsed.get("estimated_duration") or _duration_from_timeline(timeline))
    else:
        for i, entry in enumerate(timeline):
            steps.append(
                SopStep(
                    step_number=i + 1,
                    title=entry.activity or NOT_SPECIFIED,
                    description=entry.activity or NOT_SPECIFIED,
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    tools=entry.tools,
                    materials=entry.materials,
                    safety_notes=[],
                    quality_check=None,
                    visual_reference=Path(entry.frame_reference).name if entry.frame_reference else None,
                    confidence=entry.confidence,
                )
            )
        title = title_hint or clean_filename_title
        purpose = f"Standard Operating Procedure for {clean_filename_title}."
        scope = "Applies to operator procedures on standard industrial machinery."
        required_tools = _dedupe([t for entry in timeline for t in entry.tools])
        required_materials = _dedupe([m for entry in timeline for m in entry.materials])
        safety = ["Ensure standard personal protective equipment (PPE) is worn during operation."]
        quality_checks = []
        estimated_duration = _duration_from_timeline(timeline)

    sop = Sop(
        id=str(uuid.uuid4()),
        job_id=job_id,
        status="REVIEW_REQUIRED",
        title=title,
        purpose=purpose,
        scope=scope,
        required_tools=required_tools,
        required_materials=required_materials,
        safety=safety,
        steps=steps,
        quality_checks=quality_checks,
        estimated_duration=estimated_duration,
        source_video=video_filename,
    )
    save_sop(sop)
    gc.collect()
    return sop


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result


def _duration_from_timeline(timeline: List[ActivityTimelineEntry]) -> str:
    if not timeline:
        return NOT_SPECIFIED
    total_seconds = max(entry.end_time for entry in timeline) - min(entry.start_time for entry in timeline)
    if total_seconds <= 0:
        return NOT_SPECIFIED
    minutes, seconds = divmod(int(total_seconds), 60)
    if minutes:
        return f"{minutes} min {seconds} sec"
    return f"{seconds} sec"


def save_sop(sop: Sop) -> None:
    path = SOPS_DIR / f"{sop.id}.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(sop.model_dump_json(indent=2))

# 2. Elasticsearch Indexing
    elasticsearch_service.index_sop(sop)

def load_sop(sop_id: str) -> Optional[Sop]:
    path = SOPS_DIR / f"{sop_id}.json"
    if not path.exists():
        return None
    import json
    with open(path, "r", encoding="utf-8") as f:
        return Sop.model_validate(json.load(f))
