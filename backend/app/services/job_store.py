"""
JSON-file-backed job store.

There is no database in this MVP. Each job is a single JSON file at
backend/data/jobs/{job_id}.json. A per-job lock avoids corrupt writes when
the background task and a status GET race on the same file.
"""
import json
import logging
import threading
from typing import Dict, Optional

from app.config import JOBS_DIR
from app.schemas.models import STAGE_PROGRESS, Job, JobStage, JobStatus

logger = logging.getLogger(__name__)

_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(job_id: str) -> threading.Lock:
    with _locks_guard:
        if job_id not in _locks:
            _locks[job_id] = threading.Lock()
        return _locks[job_id]


def _path_for(job_id: str):
    return JOBS_DIR / f"{job_id}.json"


def save_job(job: Job) -> None:
    lock = _lock_for(job.job_id)
    with lock:
        path = _path_for(job.job_id)
        tmp_path = path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(job.model_dump_json(indent=2))
        tmp_path.replace(path)


def load_job(job_id: str) -> Optional[Job]:
    path = _path_for(job_id)
    if not path.exists():
        return None
    lock = _lock_for(job_id)
    with lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Job.model_validate(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load job %s: %s", job_id, exc)
            return None


def update_stage(job_id: str, stage: JobStage, extra_progress: Optional[int] = None) -> None:
    """Advance a job to a new stage and persist it."""
    job = load_job(job_id)
    if job is None:
        logger.warning("update_stage called for unknown job %s", job_id)
        return
    job.stage = stage
    job.progress = extra_progress if extra_progress is not None else STAGE_PROGRESS.get(stage, job.progress)
    if stage == JobStage.COMPLETED:
        job.status = JobStatus.COMPLETED
    elif stage == JobStage.ERROR:
        job.status = JobStatus.ERROR
    else:
        job.status = JobStatus.PROCESSING
    from app.schemas.models import now_iso

    job.updated_at = now_iso()
    save_job(job)


def mark_error(job_id: str, message: str) -> None:
    job = load_job(job_id)
    if job is None:
        return
    job.status = JobStatus.ERROR
    job.stage = JobStage.ERROR
    job.error_message = message
    from app.schemas.models import now_iso

    job.updated_at = now_iso()
    save_job(job)
    logger.error("Job %s failed: %s", job_id, message)
