"""
Video Validation Service

Validates video files before processing:
- Basic validity (readable, contains frames)
- FPS validation (>= 10 required)
- Duration validation (> 2 seconds AND < 5 minutes)
- Camera stability (motion detection)
- Lighting quality (brightness distribution)
- Blur detection (sharpness metrics)

Returns three status levels:
- PASS: Video is good for processing
- WARNING: Quality issues detected but processing can proceed
- ERROR: Critical issues, should not process
"""

import logging
import cv2
import numpy as np
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Tuple, List, Optional
from pathlib import Path

from app.config import (
    VIDEO_VALIDATION_MIN_FPS,
    VIDEO_VALIDATION_MIN_DURATION_SEC,
    VIDEO_VALIDATION_MAX_DURATION_SEC,
    VIDEO_VALIDATION_MIN_BRIGHTNESS,
    VIDEO_VALIDATION_MAX_BRIGHTNESS,
    VIDEO_VALIDATION_SHARPNESS_THRESHOLD,
    VIDEO_VALIDATION_BLUR_WARNING_FRAMES,
    VIDEO_VALIDATION_MOTION_THRESHOLD,
    VIDEO_VALIDATION_SAMPLE_FRAMES,
)

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    """Validation status levels"""
    PASS = "PASS"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class ValidationResult:
    """Result of video validation"""
    status: ValidationStatus
    readable: bool = True
    fps_valid: bool = True
    duration_valid: bool = True
    stable_camera: bool = True
    lighting_valid: bool = True
    blur_valid: bool = True
    fps: Optional[float] = None
    duration: Optional[float] = None
    total_frames: Optional[int] = None
    issues: List[str] = None
    details: dict = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.details is None:
            self.details = {}

    def to_dict(self):
        """Convert to dictionary for JSON response"""
        result = asdict(self)
        result['status'] = self.status.value
        return result


def validate_video(video_path: str) -> ValidationResult:
    """
    Comprehensive video validation check.

    Args:
        video_path: Path to video file

    Returns:
        ValidationResult with status and details
    """
    result = ValidationResult(status=ValidationStatus.PASS)

    # Step 1: Check file exists and is readable
    if not Path(video_path).exists():
        result.readable = False
        result.status = ValidationStatus.ERROR
        result.issues.append("Video file not found")
        return result

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            result.readable = False
            result.status = ValidationStatus.ERROR
            result.issues.append("Unable to open video file - may be corrupted or unsupported format")
            return result

        # Get video metadata
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0.0

        result.fps = round(fps, 2)
        result.duration = round(duration, 2)
        result.total_frames = total_frames

        # Step 2: Validate FPS (hard requirement)
        if fps < VIDEO_VALIDATION_MIN_FPS:
            result.fps_valid = False
            result.status = ValidationStatus.ERROR
            result.issues.append(
                f"FPS {fps:.1f} is below minimum required {VIDEO_VALIDATION_MIN_FPS}. "
                f"Video is too slow for real-time monitoring."
            )

        # Step 3: Validate duration (hard requirements)
        if duration < VIDEO_VALIDATION_MIN_DURATION_SEC:
            result.duration_valid = False
            result.status = ValidationStatus.ERROR
            result.issues.append(
                f"Duration {duration:.1f}s is below minimum {VIDEO_VALIDATION_MIN_DURATION_SEC}s"
            )
        elif duration > VIDEO_VALIDATION_MAX_DURATION_SEC:
            result.duration_valid = False
            result.status = ValidationStatus.ERROR
            result.issues.append(
                f"Duration {duration:.1f}s exceeds maximum {VIDEO_VALIDATION_MAX_DURATION_SEC}s (5 minutes)"
            )

        # Only proceed with quality checks if basic requirements pass
        if result.status != ValidationStatus.ERROR:
            # Step 4: Sample frames for quality analysis
            frame_indices = _get_sample_frame_indices(total_frames, VIDEO_VALIDATION_SAMPLE_FRAMES)

            # Step 5: Lighting validation
            lighting_issues = _validate_lighting(cap, frame_indices)
            if lighting_issues:
                result.lighting_valid = False
                result.issues.extend(lighting_issues)
                if result.status == ValidationStatus.PASS:
                    result.status = ValidationStatus.WARNING

            # Step 6: Blur detection
            blur_issues, blurry_frame_count = _detect_blur(cap, frame_indices)
            if blur_issues:
                result.blur_valid = False
                result.issues.extend(blur_issues)
                if result.status == ValidationStatus.PASS:
                    result.status = ValidationStatus.WARNING

            # Step 7: Camera stability check
            stability_issues = _check_camera_stability(cap, frame_indices)
            if stability_issues:
                result.stable_camera = False
                result.issues.extend(stability_issues)
                if result.status == ValidationStatus.PASS:
                    result.status = ValidationStatus.WARNING

        cap.release()

    except Exception as e:
        logger.error(f"Video validation error: {e}")
        result.readable = False
        result.status = ValidationStatus.ERROR
        result.issues.append(f"Validation error: {str(e)}")

    # Store details
    result.details = {
        "fps": result.fps,
        "duration_seconds": result.duration,
        "total_frames": result.total_frames,
        "sample_frames_checked": len(_get_sample_frame_indices(result.total_frames or 0, VIDEO_VALIDATION_SAMPLE_FRAMES))
    }

    logger.info(f"Video validation result: {result.status.value} - Issues: {len(result.issues)}")

    return result


def _get_sample_frame_indices(total_frames: int, num_samples: int) -> List[int]:
    """
    Get indices of frames to sample for quality checks.
    Samples at: beginning, 25%, 50%, 75%, end
    """
    if total_frames <= num_samples:
        return list(range(total_frames))

    indices = []
    for i in range(num_samples):
        # Distribute samples evenly across video
        idx = int(i * (total_frames - 1) / (num_samples - 1))
        indices.append(min(idx, total_frames - 1))

    return indices


def _validate_lighting(cap: cv2.VideoCapture, frame_indices: List[int]) -> List[str]:
    """
    Validate lighting quality by checking brightness distribution.
    Returns list of issues found (empty = OK).
    """
    issues = []
    underexposed_count = 0
    overexposed_count = 0

    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        # Convert to HSV and get Value channel (brightness)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        brightness = hsv[:, :, 2]  # V channel
        avg_brightness = np.mean(brightness)

        if avg_brightness < VIDEO_VALIDATION_MIN_BRIGHTNESS:
            underexposed_count += 1
        elif avg_brightness > VIDEO_VALIDATION_MAX_BRIGHTNESS:
            overexposed_count += 1

    if underexposed_count > 0:
        issues.append(
            f"Underexposure detected in {underexposed_count}/{len(frame_indices)} sampled frames. "
            f"Lighting is too dim for accurate detection."
        )

    if overexposed_count > 0:
        issues.append(
            f"Overexposure detected in {overexposed_count}/{len(frame_indices)} sampled frames. "
            f"Lighting is too bright, loss of detail."
        )

    return issues


def _detect_blur(cap: cv2.VideoCapture, frame_indices: List[int]) -> Tuple[List[str], int]:
    """
    Detect blur using Laplacian variance (sharpness metric).
    Returns (list of issues, count of blurry frames).
    """
    issues = []
    blurry_count = 0

    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        # Convert to grayscale and compute Laplacian variance
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        if laplacian_var < VIDEO_VALIDATION_SHARPNESS_THRESHOLD:
            blurry_count += 1

    if blurry_count >= VIDEO_VALIDATION_BLUR_WARNING_FRAMES:
        issues.append(
            f"Persistent blur detected in {blurry_count}/{len(frame_indices)} sampled frames. "
            f"Video may have focus issues or motion blur."
        )

    return issues, blurry_count


def _check_camera_stability(cap: cv2.VideoCapture, frame_indices: List[int]) -> List[str]:
    """
    Check camera stability by measuring frame-to-frame differences.
    Returns list of issues found (empty = OK).
    """
    issues = []
    unstable_pairs = 0

    prev_frame = None
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        if prev_frame is not None:
            # Compute frame difference (optical flow proxy)
            diff = cv2.absdiff(prev_frame, frame)
            mean_diff = np.mean(diff) / 255.0  # Normalize to 0-1

            if mean_diff > VIDEO_VALIDATION_MOTION_THRESHOLD:
                unstable_pairs += 1

        prev_frame = frame

    if unstable_pairs > len(frame_indices) // 3:  # More than 33% unstable transitions
        issues.append(
            f"Camera instability detected in {unstable_pairs}/{len(frame_indices)-1} frame transitions. "
            f"Excessive camera movement or shaking detected."
        )

    return issues
