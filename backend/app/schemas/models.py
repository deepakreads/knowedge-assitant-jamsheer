"""
Shared Pydantic models / JSON schema definitions.

These are used both for FastAPI response validation and as the canonical
shape of the JSON files persisted under backend/data/.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStage(str, Enum):
    UPLOADING = "uploading"
    EXTRACTING_FRAMES = "extracting_frames"
    ANALYZING_FRAMES = "analyzing_frames"
    TRANSCRIBING = "transcribing"
    OCR = "ocr"
    BUILDING_TIMELINE = "building_timeline"
    GENERATING_SOP = "generating_sop"
    COMPLETED = "completed"
    ERROR = "error"


class JobStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


STAGE_PROGRESS = {
    JobStage.UPLOADING: 10,
    JobStage.EXTRACTING_FRAMES: 25,
    JobStage.ANALYZING_FRAMES: 40,
    JobStage.TRANSCRIBING: 55,
    JobStage.OCR: 65,
    JobStage.BUILDING_TIMELINE: 75,
    JobStage.GENERATING_SOP: 90,
    JobStage.COMPLETED: 100,
    JobStage.ERROR: 0,
}


class FrameRecord(BaseModel):
    timestamp: float
    frame_number: int
    frame_path: str


class VisionObservation(BaseModel):
    timestamp: float
    frame_path: Optional[str] = None
    actions: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    text: List[str] = Field(default_factory=list)
    measurements: List[str] = Field(default_factory=list)
    safety_observations: List[str] = Field(default_factory=list)
    quality_observations: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class OcrResult(BaseModel):
    timestamp: float
    text: str
    confidence: float = 0.0


class ActivityTimelineEntry(BaseModel):
    step: int
    start_time: float
    end_time: float
    activity: str
    visual_evidence: List[str] = Field(default_factory=list)
    speech: str = ""
    ocr: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    frame_reference: Optional[str] = None


class SopStep(BaseModel):
    step_number: int
    title: str
    description: str
    start_time: float
    end_time: float
    tools: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    safety_notes: List[str] = Field(default_factory=list)
    quality_check: Optional[str] = None
    visual_reference: Optional[str] = None
    confidence: float = 0.0


class Sop(BaseModel):
    id: str
    job_id: str
    status: str = "REVIEW_REQUIRED"
    title: str
    purpose: str
    scope: str
    required_tools: List[str] = Field(default_factory=list)
    required_materials: List[str] = Field(default_factory=list)
    safety: List[str] = Field(default_factory=list)
    steps: List[SopStep] = Field(default_factory=list)
    quality_checks: List[str] = Field(default_factory=list)
    estimated_duration: str = "Not specified in the source video."
    source_video: str
    created_at: str = Field(default_factory=now_iso)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class Job(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PROCESSING
    stage: JobStage = JobStage.UPLOADING
    progress: int = 0
    video_filename: str
    video_path: str
    title: Optional[str] = None
    description: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    error_message: Optional[str] = None

    frames: List[FrameRecord] = Field(default_factory=list)
    vision_observations: List[VisionObservation] = Field(default_factory=list)
    transcript: List[TranscriptSegment] = Field(default_factory=list)
    ocr_results: List[OcrResult] = Field(default_factory=list)
    activity_timeline: List[ActivityTimelineEntry] = Field(default_factory=list)

    sop_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
