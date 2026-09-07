import logging
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
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
    violation_type: Optional[str] = None  # "out_of_order", "skipped", "incorrect", None
    expected_step: Optional[int] = None
    workflow_started: bool = False
    inactivity_alarm: bool = False  # True if no activity started within 5 seconds


class WorkflowSession:
    """Tracks a single monitoring session's workflow progression."""

    def __init__(self, sop_id: str, max_steps: int):
        self.sop_id = sop_id
        self.max_steps = max_steps
        self.session_id = str(uuid.uuid4())
        self.started_at: Optional[datetime] = None
        self.completed_steps: List[int] = []  # Steps that have been completed
        self.current_step: int = 0  # Currently active step
        self.last_detected_step: int = 0  # Last step reported by vision model
        self.workflow_initialized: bool = False  # Has operator started the workflow?
        self.violation_history: List[Dict] = []
        self.frame_count: int = 0
        self.consistent_step_count: int = 0  # Frames where same step was detected
        self.CONSISTENCY_THRESHOLD = 1  # Reduced to 1 for faster transitions
        self.step_history: List[int] = []  # Rolling history of detected steps
        self.MAX_HISTORY = 10  # Keep last N detections

        # Step state tracking for violation recovery
        self.step_violation_state: Dict[int, bool] = {}  # step_id -> has_been_violated
        self.step_active_violation: Dict[int, Optional[str]] = {}  # step_id -> current_violation_type (None if cleared)
        self.consecutive_correct_frames: int = 0  # Frames showing correct state (for stability)

        # Detection loss tracking (prevent reset on temporary occlusion/detection loss)
        self.consecutive_zero_detections: int = 0  # Frames where step == 0
        self.ZERO_DETECTION_RESET_THRESHOLD: int = 10  # Require 10 consecutive zero frames before reset

        # 5-second inactivity alarm tracking
        self.monitoring_started_at: Optional[datetime] = None  # When monitoring actually started
        self.activity_started_at: Optional[datetime] = None  # When meaningful activity was first detected
        self.inactivity_alarm_active: bool = False  # Is the 5-second inactivity alarm on?
        self.INACTIVITY_TIMEOUT_SEC: float = 5.0  # 5 seconds to start activity
    
    def backfill_missed_steps(self, detected_step: int) -> List[int]:
        """
        If we detect a step > current+1, intelligently backfill the missing steps.
        E.g., if current=0 and detect=2, backfill with 1. If current=2 and detect=4, backfill with 3.
        Returns list of backfilled step numbers.
        """
        backfilled = []
        if detected_step > self.current_step + 1:
            for step in range(self.current_step + 1, detected_step):
                if step not in self.completed_steps and step <= self.max_steps:
                    backfilled.append(step)
        return backfilled
    
    def detect_workflow_start(self, detected_step: int) -> bool:
        """
        Determine if operator has initiated workflow.
        Can start by detecting Step 1 directly, or any higher step (implies 1+ were completed).
        """
        if not self.workflow_initialized and detected_step >= 1:
            self.workflow_initialized = True
            self.started_at = datetime.utcnow()
            
            # Backfill any missed steps
            backfilled = self.backfill_missed_steps(detected_step)
            for step_num in backfilled:
                self.completed_steps.append(step_num)
            
            # Set current and add to completed
            self.current_step = detected_step
            if detected_step not in self.completed_steps:
                self.completed_steps.append(detected_step)
            
            return True
        return False
    
    def validate_step_transition(self, detected_step: int) -> tuple[bool, Optional[str]]:
        """
        Validate if detected step is a valid transition from current state.
        Returns (is_valid, violation_type)
        """
        if detected_step == 0:
            return True, None  # Idle state always allowed
        
        if not self.workflow_initialized:
            return False, None  # No violation, just waiting for start
        
        # Step must be current or advancing
        if detected_step == self.current_step:
            return True, None  # Continuing current step
        
        if detected_step == self.current_step + 1:
            return True, None  # Valid progression to next step
        
        # Out of order: detected step less than or equal to already completed
        if detected_step in self.completed_steps and detected_step < self.current_step:
            return False, "out_of_order"
        
        # Skipping steps: detected step > current + 1
        if detected_step > self.current_step + 1:
            return False, "skipped"
        
        # Regression: going backward
        if detected_step < self.current_step:
            return False, "out_of_order"
        
        return False, "unexpected"
    
    def start_monitoring(self):
        """Mark the beginning of monitoring session. Call once when monitoring starts."""
        if not self.monitoring_started_at:
            self.monitoring_started_at = datetime.utcnow()
            logger.info(f"Monitoring started for session {self.session_id}")

    def update_inactivity_alarm(self) -> bool:
        """
        Check and update 5-second inactivity alarm state.
        Returns True if alarm is currently active.
        """
        if not self.monitoring_started_at:
            return False

        # If activity hasn't started yet, check if 5 seconds have elapsed
        if not self.activity_started_at:
            elapsed = (datetime.utcnow() - self.monitoring_started_at).total_seconds()
            if elapsed >= self.INACTIVITY_TIMEOUT_SEC:
                self.inactivity_alarm_active = True
                return True
            return False

        # Activity has started, alarm is OFF
        self.inactivity_alarm_active = False
        return False

    def mark_activity_started(self):
        """Mark when user's meaningful activity begins."""
        if not self.activity_started_at:
            self.activity_started_at = datetime.utcnow()
            self.inactivity_alarm_active = False
            logger.info(f"Activity started for session {self.session_id}")

    def update_step_detection(self, detected_step: int) -> tuple[bool, Optional[Dict]]:
        """
        Process detected step with intelligent backfill for missed frames.
        Supports violation recovery: if a violated step becomes correct, the violation is cleared.
        Prevents reset on temporary detection loss.
        Returns (state_updated, violation_info)
        """
        self.frame_count += 1

        # Track step history for pattern detection
        self.step_history.append(detected_step)
        if len(self.step_history) > self.MAX_HISTORY:
            self.step_history.pop(0)

        # Track consecutive zero detections (prevent reset on temporary loss)
        if detected_step == 0:
            self.consecutive_zero_detections += 1
        else:
            self.consecutive_zero_detections = 0
            # Mark that activity has started when we detect a non-zero step
            if self.workflow_initialized or detected_step > 0:
                self.mark_activity_started()

        if detected_step == self.last_detected_step:
            self.consistent_step_count += 1
            # Track consecutive frames showing correct state (for recovery stability)
            if detected_step == self.current_step and self.step_active_violation.get(self.current_step):
                self.consecutive_correct_frames += 1
            else:
                self.consecutive_correct_frames = 0
        else:
            self.consistent_step_count = 1
            self.consecutive_correct_frames = 0
            self.last_detected_step = detected_step

        # Need consistent detection before updating state
        if self.consistent_step_count < self.CONSISTENCY_THRESHOLD:
            return False, None

        # Check if this is workflow start
        if self.detect_workflow_start(detected_step):
            return True, None

        # VIOLATION RECOVERY: Check if a previously violated step is now correct
        if (self.step_active_violation.get(self.current_step) and
            detected_step == self.current_step and
            self.consecutive_correct_frames >= 2):  # Require 2 frames of correct state
            # Step has recovered from violation
            self.step_active_violation[self.current_step] = None  # Clear active violation
            self.consecutive_correct_frames = 0
            return True, None  # Return success without violation

        # Validate transition
        is_valid, violation_type = self.validate_step_transition(detected_step)

        if not is_valid and violation_type:
            # Mark that this step has a violation
            if self.current_step not in self.step_violation_state:
                self.step_violation_state[self.current_step] = True

            # Set active violation (different from historical - this is current)
            if self.step_active_violation.get(self.current_step) != violation_type:
                self.step_active_violation[self.current_step] = violation_type

            violation = {
                "type": violation_type,
                "frame_number": self.frame_count,
                "detected_step": detected_step,
                "expected_step": self.current_step,
                "timestamp": datetime.utcnow().isoformat(),
                "has_been_violated": self.step_violation_state.get(self.current_step, False),  # Historical flag
                "is_currently_violated": True,  # Current state
            }
            self.violation_history.append(violation)
            return False, violation

        # Valid transition - handle intelligent backfill
        if detected_step > self.current_step:
            # Backfill any intermediate steps that were missed
            backfilled = self.backfill_missed_steps(detected_step)
            for step_num in backfilled:
                self.completed_steps.append(step_num)

            # Update current step - clear any violation state from previous step
            if self.current_step in self.step_active_violation:
                self.step_active_violation[self.current_step] = None

            # Move to new step
            self.current_step = detected_step
            if detected_step not in self.completed_steps:
                self.completed_steps.append(detected_step)
            self.consistent_step_count = 0
            self.consecutive_correct_frames = 0

        return True, None


# In-memory session store (in production, use Redis or database)
_sessions: Dict[str, WorkflowSession] = {}


def get_or_create_session(sop_id: str, max_steps: int) -> WorkflowSession:
    """Get existing session or create new one."""
    if sop_id not in _sessions:
        _sessions[sop_id] = WorkflowSession(sop_id, max_steps)
    return _sessions[sop_id]


def reset_session(sop_id: str):
    """Reset session for new monitoring cycle."""
    if sop_id in _sessions:
        del _sessions[sop_id]


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

    session = get_or_create_session(sop_id, len(sop.steps))
    session.start_monitoring()  # Initialize monitoring start time on first frame

    eval_dir = FRAMES_DIR / "evaluations" / sop_id
    eval_dir.mkdir(parents=True, exist_ok=True)
    temp_frame_path = eval_dir / f"frame_{uuid.uuid4()}.jpg"

    try:
        with open(temp_frame_path, "wb") as f:
            f.write(image_bytes)

        steps_summary = "\n".join([f"Step {s.step_number}: {s.title} - {s.description}" for s in sop.steps])
        max_steps = len(sop.steps)

        # Determine video type and use appropriate evaluation strategy
        video_type = sop.metadata.get("video_type", "MACHINE_INSTRUCTIONS") if sop.metadata else "MACHINE_INSTRUCTIONS"

        if video_type == "DEMO_VIDEO":
            # For DEMO_VIDEO (LEGO, simple assembly): Task-centric compliance
            from app.services import video_type_prompts
            system_prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_SYSTEM_PROMPT
            prompt = (
                f"SOP: {sop.title}\n"
                f"Steps in sequence (1→{max_steps}):\n{steps_summary}\n\n"
                f"Task compliance evaluation:\n"
                f"1. Step 0: No task in progress (idle/waiting)\n"
                f"2. Step 1+: Identify the HIGHEST step by object state (colors, positions, arrangements visible)\n"
                f"3. Ignore hand movements, wrist rotations, grip styles, approach angles\n"
                f"4. Focus on: object colors correct, positions correct, relationships correct, sequence maintained\n\n"
                f"Return ONLY valid JSON:\n"
                f'{{"compliant": boolean, "current_step_detected": "description of current task state", "step_number": int (0 to {max_steps}), "deviation_detected": boolean, "message": "audit feedback"}}'
            )
        else:
            # For MACHINE_VIDEO (industrial equipment): Process-centric compliance
            system_prompt = "You are a strict production SOP compliance auditor. Return only valid JSON."
            prompt = (
                f"You are a production-grade industrial vision system auditing strict SOP compliance.\n"
                f"SOP: {sop.title}\n"
                f"Required Steps in Strict Sequence (1→{max_steps}):\n{steps_summary}\n\n"
                f"DETECTION STRATEGY:\n"
                f"1. Step 0: Operator is idle/not yet started workflow.\n"
                f"2. Step 1+: Workflow is active. Identify the HIGHEST step number visible or in progress.\n"
                f"3. If you see evidence of later steps (tools, materials, positioning), report that higher step even if earlier steps aren't fully visible.\n"
                f"4. Example: If you see final assembly happening (Step 5), report Step 5 even if you didn't explicitly see Steps 1-4 in this frame.\n"
                f"5. This frame is ONE snapshot in a continuous workflow - use contextual reasoning about what must have happened before.\n\n"
                f"CRITICAL COMPLIANCE RULES:\n"
                f"- Steps must progress forward: 0→1→2→3...→{max_steps}. No backward movement.\n"
                f"- Report true deviation only if steps are clearly out-of-order or undoing previous work.\n"
                f"- Partial visibility of earlier steps is normal - focus on the active/current step.\n\n"
                f"Return ONLY valid JSON:\n"
                f'{{"compliant": boolean, "current_step_detected": "step name or what operator is doing now", "step_number": int (0 to {max_steps}), "deviation_detected": boolean, "message": "audit feedback"}}'
            )

        raw = ai_service.generate(
            model=VISION_MODEL,
            prompt=prompt,
            system=system_prompt,
            format_json=True,
            temperature=0.0,
            images=[str(temp_frame_path)],
        )
        parsed = ai_service.extract_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Invalid JSON response from vision model")
        
        # Extract vision model's detected step
        detected_step = int(parsed.get("step_number", 0))
        detected_step = max(0, min(detected_step, max_steps))  # Clamp to valid range
        detected_step_name = str(parsed.get("current_step_detected", ""))
        
        # Process through session state machine
        state_updated, violation_info = session.update_step_detection(detected_step)
        
        # Determine compliance based on state tracking
        has_violation = violation_info is not None
        violation_type = violation_info["type"] if violation_info else None
        expected_step = violation_info["expected_step"] if violation_info else None
        
        # Check if workflow is complete
        workflow_complete = (
            session.workflow_initialized 
            and detected_step >= max_steps 
            and len(session.completed_steps) >= max_steps
        )
        
        # Check if workflow regressed back to idle
        # IMPORTANT: Only reset after MULTIPLE frames of zero detection, not just one
        # This prevents false resets from temporary detection loss (hand occlusion, lighting change)
        workflow_regressed = (
            session.workflow_initialized
            and detected_step == 0
            and session.consecutive_zero_detections >= session.ZERO_DETECTION_RESET_THRESHOLD
        )

        # Check inactivity alarm (5-second timeout before activity starts)
        inactivity_alarm = session.update_inactivity_alarm()

        # Build response message
        if workflow_complete:
            message = "✓ WORKFLOW COMPLETE - All steps completed successfully and in correct sequence!"
            compliant = True
            deviation_detected = False
        elif workflow_regressed:
            message = "Workflow paused/reset after extended inactivity. Ready for next cycle - begin with Step 1."
            compliant = True
            deviation_detected = False
            # Reset session for new cycle
            session.workflow_initialized = False
            session.current_step = 0
            session.completed_steps = []
            session.started_at = None
            session.activity_started_at = None
            session.consecutive_zero_detections = 0
            logger.info(f"Session {session.session_id} reset after {session.consecutive_zero_detections} consecutive zero-detection frames")
        elif inactivity_alarm and not session.workflow_initialized:
            message = "⏳ No activity started (5 seconds elapsed). Please begin Step 1."
            compliant = True
            deviation_detected = False
        elif not session.workflow_initialized and detected_step == 0:
            message = "Waiting for operator to start workflow. Begin with Step 1."
            compliant = True
            deviation_detected = False
        elif not session.workflow_initialized and detected_step > 0:
            message = f"Workflow initialization detected (Step {detected_step})."
            compliant = True
            deviation_detected = False
        elif has_violation:
            if violation_type == "out_of_order":
                message = f"VIOLATION: Out-of-order step execution. Expected Step {expected_step}, detected Step {detected_step}."
            elif violation_type == "skipped":
                message = f"VIOLATION: Skipped steps detected. Expected Step {expected_step}, jumped to Step {detected_step}."
            else:
                message = f"VIOLATION: Invalid step transition to Step {detected_step}."
            compliant = False
            deviation_detected = True
        elif state_updated and detected_step > 0:
            progress = f"{len(session.completed_steps)}/{max_steps} steps completed"
            message = f"Step {session.current_step} in progress. {progress}."
            compliant = True
            deviation_detected = False
        else:
            message = f"Step {session.current_step} continuing. Monitoring active."
            compliant = True
            deviation_detected = False
        
        return FrameEvaluationResponse(
            compliant=compliant,
            current_step_detected=detected_step_name or f"Step {session.current_step}",
            step_number=session.current_step,
            deviation_detected=deviation_detected,
            message=message,
            violation_type=violation_type,
            expected_step=expected_step,
            workflow_started=session.workflow_initialized,
            inactivity_alarm=inactivity_alarm,
        )
    except Exception as exc:
        logger.exception("Camera frame evaluation failed for SOP %s: %s", sop_id, exc)
        return FrameEvaluationResponse(
            compliant=True,
            current_step_detected="Evaluation Retry",
            step_number=0,
            deviation_detected=False,
            message=f"Frame evaluation error (retrying): {str(exc)[:50]}",
            workflow_started=False,
        )
    finally:
        if temp_frame_path.exists():
            temp_frame_path.unlink(missing_ok=True)


@router.post("/sops/{sop_id}/reset-monitoring")
async def reset_monitoring(sop_id: str):
    """Reset the monitoring session for a new workflow cycle."""
    reset_session(sop_id)
    return {"status": "monitoring session reset", "sop_id": sop_id}


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
