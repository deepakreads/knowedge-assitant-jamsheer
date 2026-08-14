"""
Video upload + job status API.

POST /api/video-processing/upload           -> creates a job, kicks off background processing
GET  /api/video-processing/jobs/{job_id}     -> polls job status
"""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import ALLOWED_VIDEO_EXTENSIONS, MAX_UPLOAD_SIZE_MB, UPLOADS_DIR
from app.schemas.models import Job, JobStage, JobStatus
from app.services import job_store
from app.services.pipeline_service import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video-processing", tags=["video-processing"])

MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. Allowed: {sorted(ALLOWED_VIDEO_EXTENSIONS)}",
        )

    job_id = str(uuid.uuid4())
    saved_filename = f"{job_id}{extension}"
    saved_path = UPLOADS_DIR / saved_filename

    size = 0
    try:
        with open(saved_path, "wb") as out_file:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE_BYTES:
                    out_file.close()
                    saved_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {MAX_UPLOAD_SIZE_MB}MB upload limit.",
                    )
                out_file.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        logger.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}") from exc

    if size == 0:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    job = Job(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        stage=JobStage.UPLOADING,
        progress=10,
        video_filename=file.filename or saved_filename,
        video_path=str(saved_path),
        title=title,
        description=description,
    )
    job_store.save_job(job)

    background_tasks.add_task(run_pipeline, job_id)

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "processing", "progress": 0},
    )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = job_store.load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    response = {
        "job_id": job.job_id,
        "status": job.status.value,
        "progress": job.progress,
        "stage": job.stage.value,
    }

    if job.status == JobStatus.ERROR:
        response["error_message"] = job.error_message

    if job.status == JobStatus.COMPLETED:
        response["sop_generated"] = job.sop_id is not None
        response["sop_id"] = job.sop_id
        sop_steps = []
        if job.sop_id:
            from app.services import sop_service

            sop = sop_service.load_sop(job.sop_id)
            if sop:
                sop_steps = [step.model_dump() for step in sop.steps]
        response["sop_steps"] = sop_steps

    return response
