import gc
import logging
import time

from app.config import SOP_MODEL, VISION_MODEL
from app.schemas.models import Job, JobStage
from app.services import (
    activity_service,
    job_store,
    ocr_service,
    sop_service,
    transcription_service,
    validation_service,
    video_service,
    vision_service,
    video_type_analyzer,
)

logger = logging.getLogger(__name__)


def run_pipeline(job_id: str) -> None:
    job = job_store.load_job(job_id)
    if job is None:
        logger.error("run_pipeline: job %s not found", job_id)
        return

    start_time = time.time()
    logger.info("==================================================")
    logger.info("STARTING PIPELINE FOR JOB: %s", job_id)
    logger.info("==================================================")

    try:
        _run(job)
        elapsed = time.time() - start_time
        logger.info("==================================================")
        logger.info("JOB %s COMPLETED SUCCESSFULLY IN %.2f SECONDS", job_id, elapsed)
        logger.info("==================================================")
    except Exception as exc:
        logger.exception("Pipeline crashed for job %s: %s", job_id, exc)
        job_store.mark_error(job_id, f"Processing failed: {exc}")
    finally:
        gc.collect()


def _run(job: Job) -> None:
    job_id = job.job_id

    # --- Stage 1: Validating Video ---
    logger.info("[Stage 1/7] Validating video file for job %s...", job_id)
    job_store.update_stage(job_id, JobStage.VALIDATING)

    validation_result = validation_service.validate_video(job.video_path)
    logger.info("Video validation result: %s", validation_result.status.value)

    for issue in validation_result.issues:
        logger.info("  - %s", issue)

    # Store validation details in job metadata
    job = job_store.load_job(job_id)
    if job.metadata is None:
        job.metadata = {}
    job.metadata["validation_result"] = validation_result.to_dict()
    job_store.save_job(job)

    # ERROR status means validation failed - cannot process
    if validation_result.status == validation_service.ValidationStatus.ERROR:
        error_msg = "Video validation failed: " + "; ".join(validation_result.issues)
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # WARNING status means issues but can continue
    if validation_result.status == validation_service.ValidationStatus.WARNING:
        logger.warning("Video has quality warnings but will proceed: %s",
                      "; ".join(validation_result.issues))

    # --- Stage 2: Extracting Frames ---
    logger.info("[Stage 2/7] Extracting frames for job %s...", job_id)
    job_store.update_stage(job_id, JobStage.EXTRACTING_FRAMES)
    frames, metadata = video_service.extract_frames(job.video_path, job_id)
    
    job = job_store.load_job(job_id)
    job.frames = frames
    job_store.save_job(job)
    logger.info("Job %s: extracted %d sampled frames.", job_id, len(frames))

    # --- Stage 3: Analyzing Frames (Vision) ---
    logger.info("[Stage 3/7] Analyzing frames visually with %s...", VISION_MODEL)
    job_store.update_stage(job_id, JobStage.ANALYZING_FRAMES)
    vision_observations = vision_service.analyze_frames(frames)

    gc.collect()

    if not vision_observations:
        raise RuntimeError("Visual analysis produced no usable observations for any frame.")

    job = job_store.load_job(job_id)
    job.vision_observations = vision_observations
    job_store.save_job(job)
    logger.info("Job %s: visual analysis complete (%d observations).", job_id, len(vision_observations))

    # --- Stage 3.5: Video Type Classification (NEW) ---
    logger.info("[Stage 3.5/7] Classifying video type...")
    video_type_info = video_type_analyzer.VideoTypeAnalyzer.analyze_video_type(vision_observations)

    logger.info(
        "Job %s: Video type = %s (confidence: %.2f)",
        job_id,
        video_type_info["type"],
        video_type_info["confidence"]
    )
    logger.info("Job %s: Key indicators = %s", job_id, ", ".join(video_type_info["key_indicators"]))

    # Store video type in job metadata
    job = job_store.load_job(job_id)
    if job.metadata is None:
        job.metadata = {}
    job.metadata["video_type"] = str(video_type_info["type"])
    job.metadata["video_type_confidence"] = video_type_info["confidence"]
    job.metadata["video_type_indicators"] = video_type_info["key_indicators"]
    job_store.save_job(job)

    # --- Stage 5: Transcribing Audio (Non-fatal) ---
    logger.info("[Stage 5/7] Extracting and transcribing audio...")
    job_store.update_stage(job_id, JobStage.TRANSCRIBING)
    transcript = []
    try:
        audio_path = video_service.extract_audio(job.video_path, job_id)
        transcript = transcription_service.transcribe_audio(audio_path)
    except Exception as exc:
        logger.warning("Job %s: transcription failed, continuing without audio: %s", job_id, exc)

    job = job_store.load_job(job_id)
    job.transcript = transcript
    job_store.save_job(job)

    # --- Stage 6: OCR (Non-fatal) ---
    logger.info("[Stage 6/7] Running OCR on sampled frames...")
    job_store.update_stage(job_id, JobStage.OCR)
    ocr_results = []
    try:
        ocr_results = ocr_service.run_ocr_on_frames(frames)
    except Exception as exc:
        logger.warning("Job %s: OCR failed, continuing without OCR: %s", job_id, exc)

    job = job_store.load_job(job_id)
    job.ocr_results = ocr_results
    job_store.save_job(job)

    # --- Stage 7: Building Activity Timeline (with video type-specific prompts) ---
    logger.info("[Stage 7/7] Building activity timeline with %s (video type: %s)...", SOP_MODEL, video_type_info["type"])
    job_store.update_stage(job_id, JobStage.BUILDING_TIMELINE)
    timeline = activity_service.build_activity_timeline(
        vision_observations,
        transcript,
        ocr_results,
        video_type=video_type_info["type"]
    )

    if not timeline:
        raise RuntimeError("Could not build an activity timeline from the extracted evidence.")

    job = job_store.load_job(job_id)
    job.activity_timeline = timeline
    job_store.save_job(job)
    logger.info("Job %s: built activity timeline with %d activities.", job_id, len(timeline))

    # --- Stage 8: Generating SOP (with video type-specific prompts) ---
    logger.info("[Stage 8/8] Generating final SOP with %s (video type: %s)...", SOP_MODEL, video_type_info["type"])
    job_store.update_stage(job_id, JobStage.GENERATING_SOP)
    sop = sop_service.generate_sop(
        job_id=job_id,
        video_filename=job.video_filename,
        timeline=timeline,
        title_hint=job.title,
        metadata=job.metadata,
        video_type=video_type_info["type"],
    )

    gc.collect()

    job = job_store.load_job(job_id)
    job.sop_id = sop.id
    job_store.save_job(job)

    # --- Completed ---
    job_store.update_stage(job_id, JobStage.COMPLETED)
    logger.info("Job %s: stage marked COMPLETED. SOP ID: %s", job_id, sop.id)
