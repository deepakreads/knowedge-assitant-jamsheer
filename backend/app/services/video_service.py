import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

import cv2

from app.config import FRAMES_DIR, MAX_FRAMES_TO_ANALYZE
from app.schemas.models import FrameRecord

logger = logging.getLogger(__name__)


def extract_frames(video_path: str, job_id: str) -> Tuple[List[FrameRecord], Dict[str, float]]:
    job_frame_dir = FRAMES_DIR / job_id
    job_frame_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0.0

    target_count = min(MAX_FRAMES_TO_ANALYZE, max(3, total_frames))
    
    if total_frames <= target_count:
        frame_indices = list(range(total_frames))
    else:
        step = total_frames / float(target_count)
        frame_indices = [int(i * step) for i in range(target_count)]

    frame_records: List[FrameRecord] = []
    
    for count, idx in enumerate(frame_indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        timestamp = round(idx / fps, 2)
        frame_filename = f"frame_{count:04d}_{idx}.jpg"
        frame_path = job_frame_dir / frame_filename

        cv2.imwrite(str(frame_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

        frame_records.append(
            FrameRecord(
                timestamp=timestamp,
                frame_number=idx,
                frame_path=str(frame_path),
            )
        )

    cap.release()

    if not frame_records:
        raise RuntimeError("Failed to extract any valid frames from the video.")

    metadata = {
        "duration_seconds": round(duration, 2),
        "total_frames": total_frames,
        "fps": round(fps, 2),
        "sampled_frames": len(frame_records),
    }

    logger.info("Extracted %d frames from video (duration: %.1fs)", len(frame_records), duration)
    return frame_records, metadata


def extract_audio(video_path: str, job_id: str) -> str:
    audio_path = FRAMES_DIR / job_id / "audio.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(audio_path),
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)
        return str(audio_path)
    except Exception as exc:
        logger.warning("Audio extraction via ffmpeg failed or timed out: %s", exc)
        raise RuntimeError(f"Audio extraction failed: {exc}") from exc