import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from app.services import pdf_service, sop_service, ai_service
from app.config import VISION_MODEL, FRAMES_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sop-generation", tags=["SOP Generation"])


class FrameEvaluationResponse(BaseModel):
    compliant: bool = True
    current_step_detected: str = "Waiting for initial step"
    step_number: int = Field(default=0, ge=0)
    deviation_detected: bool = False
    message: str = "Monitoring active."


@router.get("/sops/{sop_id}")
async def get_sop(sop_id: str):
    sop = sop_service.load_sop(sop_id)
    if sop is None:
        raise HTTPException(status_code=404, detail="SOP not found.")
    return sop


@router.post("/sops/{sop_id}/evaluate-frame", response_model=FrameEvaluationResponse)
async def evaluate_camera_frame(sop_id: str, file: UploadFile = File(...)):
    sop = sop_service.load_sop(sop_id)
    if sop is None:
        raise HTTPException(status_code=404, detail="SOP not found.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty frame received.")

    eval_dir = FRAMES_DIR / "evaluations" / sop_id
    eval_dir.mkdir(parents=True, exist_ok=True)
    temp_frame_path = eval_dir / f"frame_{uuid.uuid4()}.jpg"
    
    try:
        with open(temp_frame_path, "wb") as f:
            f.write(image_bytes)

        steps_summary = "\n".join([f"Step {s.step_number}: {s.title} - {s.description}" for s in sop.steps])
        max_steps = len(sop.steps)
        
        prompt = (
            f"You are an expert production-grade industrial computer vision auditor.\n"
            f"Target SOP Title: {sop.title}\n"
            f"Authorized Procedure Steps in Strict Order (1 to {max_steps}):\n{steps_summary}\n\n"
            f"Analyze the operator in this live camera frame:\n"
            f"1. Check if the operator has initiated Step 1 yet. If completely unstarted/idle before beginning, set step_number to 0.\n"
            f"2. Once the workflow has started, determine the exact active step number (1 to {max_steps}). Never drop back to 0 once work has commenced; if between tasks, hold the last active step number.\n"
            f"3. Strict Enforcement: If steps are performed out of order, skipped entirely, or if unauthorized actions occur, set 'deviation_detected': true and 'compliant': false with a clear explanation.\n\n"
            f"Return ONLY valid JSON with this exact schema:\n"
            f'{{"compliant": true/false, "current_step_detected": "name of active step", "step_number": integer from 0 to {max_steps}, "deviation_detected": true/false, "message": "detailed audit feedback"}}'
        )

        raw = ai_service.generate(
            model=VISION_MODEL,
            prompt=prompt,
            system="You are an industrial SOP sequence compliance monitor. Return strict JSON.",
            format_json=True,
            temperature=0.0,
            images=[str(temp_frame_path)],
        )
        parsed = ai_service.extract_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Invalid JSON response from vision model")
            
        detected_step = int(parsed.get("step_number", 0))
        if detected_step < 0 or detected_step > max_steps:
            detected_step = 0

        return FrameEvaluationResponse(
            compliant=bool(parsed.get("compliant", True)),
            current_step_detected=str(parsed.get("current_step_detected", "Active Monitoring")),
            step_number=detected_step,
            deviation_detected=bool(parsed.get("deviation_detected", False)),
            message=str(parsed.get("message", "Monitoring active.")),
        )
    except Exception as exc:
        logger.exception("Camera frame evaluation failed for SOP %s: %s", sop_id, exc)
        return FrameEvaluationResponse(
            compliant=True,
            current_step_detected="Temporary Evaluation Retrying...",
            step_number=0,
            deviation_detected=False,
            message=f"Frame skipped due to temporary evaluation error: {exc}",
        )
    finally:
        if temp_frame_path.exists():
            temp_frame_path.unlink(missing_ok=True)


@router.get("/sops/{sop_id}/pdf")
async def download_sop_pdf(sop_id: str):
    sop = sop_service.load_sop(sop_id)
    if sop is None:
        raise HTTPException(status_code=404, detail="SOP not found.")

    try:
        pdf_bytes = pdf_service.generate_sop_pdf(sop)
        filename = f"SOP_{sop.title.replace(' ', '_')}_{sop_id[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as exc:
        logger.exception("Failed to generate PDF for SOP %s: %s", sop_id, exc)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")