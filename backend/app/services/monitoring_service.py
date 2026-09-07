import time
import logging
import base64
import io
import hashlib
from typing import Dict, List, Optional
from PIL import Image

logger = logging.getLogger(__name__)


class SOPMonitoringService:
    """Real-time SOP compliance monitoring with vision-based analysis"""

    def __init__(self, sop: dict, focus_major_steps: bool = True):
        """
        Initialize monitoring service for a specific SOP

        Args:
            sop: The SOP data dictionary
            focus_major_steps: If True, only evaluate major steps for compliance.
                              Minor steps are skipped automatically.
        """
        self.sop = sop
        self.current_step = 0
        self.step_start_time = time.time()
        self.compliance_history = []
        self.total_compliance = 0
        self.frames_analyzed = 0
        self.focus_major_steps = focus_major_steps

        # Violation recovery tracking
        self.step_violation_state: Dict[int, bool] = {}  # step_index -> has_been_violated (historical)
        self.step_active_violation: Dict[int, bool] = {}  # step_index -> is_currently_violated (current)
        self.step_compliance_history: Dict[int, List[float]] = {}  # step_index -> list of compliance scores
        self.step_recovery_frames: int = 0  # Frames showing good compliance after violation

        # Response caching for faster feedback (Level 2 optimization)
        self.response_cache: Dict[int, Dict] = {}  # step_index -> cached response
        self.response_cache_time: Dict[int, float] = {}  # step_index -> cache time
        self.cache_ttl_ms: int = 300  # Cache TTL: 300ms for instant feedback on static scenes

        # Frame similarity detection for smart filtering (Level 3 optimization)
        self.last_frame_hash: Optional[str] = None  # Hash of previous frame
        self.frame_skip_count: int = 0  # Count of skipped identical frames
        self.frame_change_threshold: int = 2  # Skip after N identical frames
        self.similarity_skip_enabled: bool = True  # Enable/disable frame similarity

        # Identify major steps on initialization
        self.major_step_indices = self._identify_major_steps() if focus_major_steps else None

        logger.info(f"Initialized monitoring for SOP: {sop.get('title', 'Unknown')}")
        if focus_major_steps and self.major_step_indices:
            logger.info(
                f"Major step mode: focusing on {len(self.major_step_indices)} major steps "
                f"out of {len(sop.get('steps', []))} total steps"
            )

    async def analyze_frame(self, frame_base64: str) -> Dict:
        """
        Analyze current frame against current SOP step.

        If focus_major_steps is enabled, automatically skips minor steps.

        Returns:
            {
                "current_step": int,
                "total_steps": int,
                "major_steps_count": int (if major step mode),
                "is_major_step": bool (if major step mode),
                "step_title": str,
                "compliance": float (0-100),
                "overall_compliance": float (0-100),
                "feedback": str,
                "next_step_ready": bool,
                "warnings": list,
                "time_remaining": int (seconds),
                "progress_percent": float (0-100)
            }
        """
        try:
            if self.current_step >= len(self.sop.get("steps", [])):
                return self._create_completion_response()

            current_step = self.sop["steps"][self.current_step]

            # Check if this is a major step (if major step mode enabled)
            is_major_step = self._is_major_step(self.current_step)

            # If minor step mode and not a major step, skip to next
            if self.focus_major_steps and not is_major_step:
                logger.info(f"Skipping minor step: {current_step.get('title', 'Unknown')}")
                self._advance_step()
                # Recursively analyze next frame for the next step
                return await self.analyze_frame(frame_base64)

            # FRAME SIMILARITY CHECK: Skip analysis for identical frames (Level 3 optimization)
            # Computes quick hash to detect motion without full analysis
            if self.similarity_skip_enabled:
                current_frame_hash = hashlib.md5(
                    frame_base64.encode() if isinstance(frame_base64, str) else frame_base64
                ).hexdigest()

                if self.last_frame_hash == current_frame_hash:
                    # Frame identical to last one - user not moving
                    self.frame_skip_count += 1
                    logger.debug(f"Frame identical (skip #{self.frame_skip_count}) - using cache if available")

                    # If we've seen enough identical frames AND have cached result, skip analysis
                    if self.frame_skip_count >= self.frame_change_threshold and \
                       self.current_step in self.response_cache and \
                       self.step_active_violation.get(self.current_step, False) is False:
                        # Return cached result without re-analysis
                        cached_result = self.response_cache[self.current_step]
                        logger.debug(f"Skipped analysis for step {self.current_step + 1} (identical frame)")
                        return cached_result
                else:
                    # Frame changed - reset skip counter AND clear cache (force fresh analysis)
                    self.last_frame_hash = current_frame_hash
                    self.frame_skip_count = 0

                    # Clear Level 2 cache when frame content changes to force fresh analysis
                    if self.current_step in self.response_cache:
                        del self.response_cache[self.current_step]
                    if self.current_step in self.response_cache_time:
                        del self.response_cache_time[self.current_step]

                    logger.debug(f"Frame changed - resetting skip counter and cache, new hash: {current_frame_hash[:8]}...")

            # CHECK CACHE: Return cached result only if fresh, stable state, and NOT in recovery (Level 2 optimization)
            # NOTE: Cache is only used for stable/compliant states (>= 80), NOT for violation recovery
            # This ensures violations are always detected, but stable scenes get fast feedback
            cache_key = self.current_step
            current_time_ms = time.time() * 1000
            was_violated = self.step_active_violation.get(self.current_step, False)

            if cache_key in self.response_cache and cache_key in self.response_cache_time and not was_violated:
                cached_compliance = self.response_cache[cache_key].get("compliance", 0)
                # Only use cache if: (1) cache is fresh, (2) cached state was stable (no violation),
                # AND (3) we're not currently recovering from a violation
                if cached_compliance >= 80:
                    cache_age_ms = current_time_ms - self.response_cache_time[cache_key]
                    if cache_age_ms < self.cache_ttl_ms:
                        # Cache hit for stable state - return immediately without vision API call
                        logger.debug(f"Cache hit for step {self.current_step + 1} (age: {cache_age_ms:.0f}ms, compliance: {cached_compliance})")
                        return self.response_cache[cache_key]

            # Analyze the frame using vision AI (for major steps only)
            compliance = await self._analyze_frame_with_vision(frame_base64, current_step)

            # Track compliance history per step (for violation recovery)
            if self.current_step not in self.step_compliance_history:
                self.step_compliance_history[self.current_step] = []
            self.step_compliance_history[self.current_step].append(compliance)

            # VIOLATION RECOVERY: Check if a previously violated step is now correct
            was_violated = self.step_active_violation.get(self.current_step, False)
            is_now_compliant = compliance >= 80  # Task is compliant if score >= 80

            if was_violated and is_now_compliant:
                # Step has recovered from violation
                self.step_recovery_frames += 1
                if self.step_recovery_frames >= 2:  # Require 2 frames of good compliance
                    # Clear the active violation
                    self.step_active_violation[self.current_step] = False
                    self.step_recovery_frames = 0
                    logger.info(f"Step {self.current_step + 1} recovered from violation (compliance: {compliance}%)")
            elif not is_now_compliant:
                # Step is still violating
                if self.current_step not in self.step_violation_state:
                    self.step_violation_state[self.current_step] = True  # Mark historical violation
                self.step_active_violation[self.current_step] = True
                self.step_recovery_frames = 0
            else:
                # Compliance is good, reset recovery counter
                if not was_violated:
                    self.step_recovery_frames = 0

            # Generate feedback
            feedback = self._generate_feedback(compliance, current_step)

            # Check if step should auto-advance
            # Only advance if current step is NOT violated OR has recovered from violation
            is_currently_violated = self.step_active_violation.get(self.current_step, False)
            step_complete = self._check_step_complete(current_step) and not is_currently_violated
            if step_complete:
                self._advance_step()

            # Track compliance history (only for major steps)
            self.compliance_history.append(compliance)
            self.frames_analyzed += 1
            self.total_compliance = sum(self.compliance_history) / len(self.compliance_history)

            # Calculate progress based on major steps if applicable
            if self.focus_major_steps and self.major_step_indices:
                progress_percent = (self.major_step_indices.index(self.current_step) / len(self.major_step_indices)) * 100 if self.current_step in self.major_step_indices else 0
            else:
                progress_percent = (self.current_step / len(self.sop["steps"])) * 100

            result = {
                "current_step": self.current_step + 1,
                "total_steps": len(self.sop.get("steps", [])),
                "step_title": current_step.get("title", "Unknown"),
                "step_description": current_step.get("description", ""),
                "compliance": round(compliance, 1),
                "overall_compliance": round(self.total_compliance, 1),
                "feedback": feedback,
                "next_step_ready": step_complete,
                "warnings": self._get_warnings(compliance, current_step),
                "time_remaining": self._get_time_remaining(current_step),
                "progress_percent": round(progress_percent, 1),
                "tools_required": current_step.get("tools", []),
                "step_number": self.current_step + 1,
            }

            # Add major step info if applicable
            if self.focus_major_steps:
                result["is_major_step"] = is_major_step
                result["major_steps_count"] = len(self.major_step_indices) if self.major_step_indices else 0

            # STORE IN CACHE: Save result ONLY for stable states (>= 80 compliance) (Level 2 optimization)
            # Violation states are NOT cached to ensure violations are always detected fresh
            if compliance >= 80:
                self.response_cache[cache_key] = result
                self.response_cache_time[cache_key] = current_time_ms
                logger.debug(f"Cached result for step {result['current_step']} (compliance: {compliance})")
            else:
                # Clear cache for violation states to ensure fresh analysis next time
                if cache_key in self.response_cache:
                    del self.response_cache[cache_key]
                if cache_key in self.response_cache_time:
                    del self.response_cache_time[cache_key]
                logger.debug(f"Violation state not cached (compliance: {compliance})")

            logger.debug(f"Frame analysis complete - Step {result['current_step']}, Compliance: {compliance}%")
            return result

        except Exception as e:
            logger.error(f"Error analyzing frame: {e}")
            return {
                "error": str(e),
                "current_step": self.current_step + 1,
                "total_steps": len(self.sop.get("steps", [])),
                "compliance": 0,
                "overall_compliance": round(self.total_compliance, 1) if self.total_compliance > 0 else 0,
            }

    def _calculate_compliance(self, step: dict) -> float:
        """
        Calculate compliance score (0-100) based on step progress

        Scoring factors:
        - Time spent on step (0-60 points)
        - Tool presence (0-20 points)
        - Safety compliance (0-20 points)
        """
        score = 0
        elapsed = time.time() - self.step_start_time
        expected_duration = step.get("duration", 30)

        # Time-based scoring (up to 60 points)
        # Linear progress up to expected duration
        if expected_duration > 0:
            time_percent = min(100, (elapsed / expected_duration) * 100)
            score += (time_percent / 100) * 60

        # Tool verification (20 points)
        # In full implementation, this would be from vision analysis
        tools = step.get("tools", [])
        if not tools:
            score += 20  # No tools required, full points
        else:
            score += 10  # Partial credit for having tools

        # Safety compliance (20 points)
        # In full implementation, would check for unsafe actions
        score += 15  # Default safe behavior assumption

        return min(100, max(0, score))

    def _generate_feedback(self, compliance: float, step: dict) -> str:
        """Generate user-friendly guidance based on compliance"""
        step_title = step.get("title", "Current step")
        description = step.get("description", "")

        if compliance >= 80:
            return f"✅ Great! You're following the procedure correctly. Continue with: {step_title}"
        elif compliance >= 60:
            return f"⚠️ Good progress. Make sure to: {description}"
        elif compliance >= 40:
            return f"⏱️ You're working on it. Required steps: {', '.join(step.get('tools', [])[:2])}"
        else:
            return f"👉 Let's focus on: {step_title}. {description}"

    def _check_step_complete(self, step: dict) -> bool:
        """Check if current step is complete based on elapsed time"""
        elapsed = time.time() - self.step_start_time
        min_duration = step.get("duration", 30)

        # Step complete if elapsed >= 80% of expected duration
        return elapsed >= (min_duration * 0.8)

    def _advance_step(self):
        """Move to next step"""
        if self.current_step < len(self.sop.get("steps", [])) - 1:
            prev_step = self.sop["steps"][self.current_step].get("title", "Unknown")
            self.current_step += 1
            self.step_start_time = time.time()
            next_step = self.sop["steps"][self.current_step].get("title", "Unknown")
            logger.info(f"Advanced from '{prev_step}' to '{next_step}' (Step {self.current_step + 1})")

            # Clear cache for new step to ensure fresh analysis
            if self.current_step in self.response_cache:
                del self.response_cache[self.current_step]
            if self.current_step in self.response_cache_time:
                del self.response_cache_time[self.current_step]

            # Reset frame similarity tracking for new step
            self.last_frame_hash = None
            self.frame_skip_count = 0
        else:
            logger.info("All steps completed!")

    def _get_warnings(self, compliance: float, step: dict) -> List[str]:
        """Extract safety or procedural warnings - only for active violations, not historical"""
        warnings = []

        # Only show compliance warning if this is an ACTIVE violation, not a historical one
        is_currently_violated = self.step_active_violation.get(self.current_step, False)
        if compliance < 40 and is_currently_violated:
            warnings.append("⚠️ Low compliance - check procedure")
        elif compliance < 40 and compliance >= 20:
            warnings.append("⚡ Compliance recovering - continue...")
        elif compliance < 20 and not is_currently_violated:
            # This shouldn't happen, but handle edge case
            pass

        if step.get("safety_notes"):
            warnings.append(f"🚨 {step['safety_notes']}")

        return warnings

    def _get_time_remaining(self, step: dict) -> int:
        """Calculate estimated time remaining for current step"""
        elapsed = time.time() - self.step_start_time
        expected = step.get("duration", 60)
        remaining = max(0, int(expected - elapsed))
        return remaining

    def _create_completion_response(self) -> Dict:
        """Create response when all steps are completed"""
        return {
            "current_step": len(self.sop.get("steps", [])),
            "total_steps": len(self.sop.get("steps", [])),
            "step_title": "Procedure Complete! ✅",
            "compliance": 100,
            "overall_compliance": round(self.total_compliance, 1) if self.total_compliance > 0 else 100,
            "feedback": "🎉 Excellent work! You've completed the entire procedure successfully.",
            "next_step_ready": True,
            "warnings": [],
            "time_remaining": 0,
            "progress_percent": 100,
            "completed": True,
        }

    async def _analyze_frame_with_vision(self, frame_base64: str, step: dict) -> float:
        """
        Analyze frame using vision AI and compare against SOP step.

        Returns compliance score 0-100.

        Uses video-type-aware prompts to focus on task state (objects) rather than hand movements.
        """
        try:
            from app.services import vision_service, video_type_prompts

            # Determine video type from SOP metadata
            video_type = self.sop.get("metadata", {}).get("video_type", "MACHINE_INSTRUCTIONS") if self.sop.get("metadata") else "MACHINE_INSTRUCTIONS"

            # Create video-type-specific prompt
            if video_type == "DEMO_VIDEO":
                # Task/Object-centric compliance for LEGO, simple assembly, etc.
                required_materials_str = ", ".join(step.get("materials", [])) or "no specific materials"
                prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE.format(
                    step_title=step.get("title", "Unknown"),
                    step_description=step.get("description", ""),
                    required_objects=required_materials_str
                )
                analysis_type = "object_state"
            else:
                # Equipment/Process-centric compliance for industrial machinery
                tools_str = ", ".join(step.get("tools", [])) or "no specific tools"
                prompt = video_type_prompts.MACHINE_VIDEO_COMPLIANCE_PROMPT_TEMPLATE.format(
                    step_title=step.get("title", "Unknown"),
                    step_description=step.get("description", ""),
                    required_tools=tools_str
                )
                analysis_type = "equipment_state"

            # Send frame to vision service
            logger.info(f"Analyzing frame for step: {step.get('title', 'Unknown')} (video_type={video_type})")
            analysis = await vision_service.analyze_frame_with_prompt(
                frame_base64,
                prompt
            )

            # Parse the analysis to calculate compliance
            compliance = self._parse_vision_analysis(analysis, step, analysis_type)
            logger.info(f"Frame compliance: {compliance}% (analysis_type={analysis_type})")

            return compliance

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            # Fallback to time-based compliance if vision fails
            return self._calculate_compliance(step)

    def _parse_vision_analysis(self, analysis: str, step: dict, analysis_type: str = "equipment_state") -> float:
        """
        Parse vision AI response and calculate compliance score.

        DEBUG: Log all vision responses to diagnose detection issues.

        Args:
            analysis: Vision AI response (JSON string)
            step: Current SOP step
            analysis_type: Type of analysis ("object_state" for DEMO_VIDEO, "equipment_state" for MACHINE_VIDEO)

        Scoring for DEMO_VIDEO (object_state):
        - If task_compliant=True: Score based on individual checks
        - If task_compliant=False: Cap score at 40 (violation detected)
        - Objects present: 25 points
        - Objects colors correct: 25 points
        - Objects positioned correctly: 30 points
        - Objects oriented correctly: 20 points

        Scoring for MACHINE_VIDEO (equipment_state):
        - If process_compliant=True: Full scoring available
        - If process_compliant=False: Cap score at 45
        - Equipment present: 20 points
        - Equipment active: 25 points
        - Parameters correct: 25 points
        - Material state correct: 30 points
        """
        try:
            import json
            parsed = json.loads(analysis) if isinstance(analysis, str) else analysis
        except (json.JSONDecodeError, TypeError):
            # Fallback to text parsing if JSON parse fails
            parsed = {}
            logger.warning(f"Failed to parse vision analysis: {analysis}")

        score = 0

        if analysis_type == "object_state":
            # DEMO_VIDEO: Focus on object state, NOT hand movements
            # The vision response should have: required_objects_present, object_colors_correct,
            # object_positioning_correct, object_orientation_correct, task_compliant

            objects_present = parsed.get("required_objects_present", False)
            colors_correct = parsed.get("object_colors_correct", False)
            positioning_correct = parsed.get("object_positioning_correct", False)
            orientation_correct = parsed.get("object_orientation_correct", True)
            task_compliant = parsed.get("task_compliant", False)

            # DEBUG: Log each check
            logger.debug(f"Vision analysis (DEMO_VIDEO):")
            logger.debug(f"  objects_present: {objects_present}")
            logger.debug(f"  colors_correct: {colors_correct}")
            logger.debug(f"  positioning_correct: {positioning_correct}")
            logger.debug(f"  orientation_correct: {orientation_correct}")
            logger.debug(f"  task_compliant: {task_compliant}")

            if objects_present:
                score += 25
            if colors_correct:
                score += 25
            if positioning_correct:
                score += 30
            if orientation_correct:
                score += 20

            # CRITICAL: If task is not compliant, cap score (violation detected)
            if not task_compliant:
                score = min(40, score)  # Cap at 40 for violation
                logger.warning(f"Violation detected: task_compliant=False, score capped to {score}%")
            else:
                # Bonus if task compliant: up to 100
                score = min(100, score + 10)
                logger.debug(f"Task compliant, score: {score}%")

            # The key insight: IGNORE ignored_hand_movements field
            # If hand movements were ignored but objects are correct, that's SUCCESS
            if parsed.get("ignored_hand_movements", False) and score >= 80:
                score = min(100, score + 5)  # Slight bonus for correct evaluation

        else:
            # MACHINE_VIDEO: Focus on equipment/process state
            # The vision response should have: equipment_present, equipment_active,
            # parameters_correct, material_state_correct, process_compliant

            if parsed.get("equipment_present", False):
                score += 20
            if parsed.get("equipment_active", False):
                score += 25
            if parsed.get("parameters_correct", False):
                score += 25
            if parsed.get("material_state_correct", False):
                score += 30

            # CRITICAL: If process not compliant, cap score (violation detected)
            process_compliant = parsed.get("process_compliant", False)
            if not process_compliant:
                score = min(45, score)  # Cap at 45 for violation
            else:
                # Bonus if process compliant: up to 100
                score = min(100, score + 10)

        return min(100, max(0, score))

    def get_session_summary(self) -> Dict:
        """Get summary of monitoring session"""
        return {
            "total_steps": len(self.sop.get("steps", [])),
            "current_step": self.current_step + 1,
            "overall_compliance": round(self.total_compliance, 1) if self.total_compliance > 0 else 0,
            "frames_analyzed": self.frames_analyzed,
            "completed": self.current_step >= len(self.sop.get("steps", [])),
        }

    def _identify_major_steps(self) -> List[int]:
        """
        Identify which steps are "major" steps for compliance evaluation.

        A step is considered "major" if ANY of these conditions are true:
        1. Has safety notes (safety-critical)
        2. Has tools required (manual/hands-on work)
        3. Duration > 30 seconds (significant operation)
        4. Has quality check requirements
        5. Explicitly marked as important

        Returns: List of step indices (0-based) that are major
        """
        major_indices = []
        steps = self.sop.get("steps", [])

        for idx, step in enumerate(steps):
            is_major = False

            # Check safety notes
            if step.get("safety_notes"):
                is_major = True
                logger.debug(f"Step {idx + 1} '{step.get('title')}': Major (safety-critical)")

            # Check tools required
            if step.get("tools"):
                is_major = True
                logger.debug(f"Step {idx + 1} '{step.get('title')}': Major (has tools)")

            # Check duration
            duration = step.get("duration", 0)
            if duration > 30:
                is_major = True
                logger.debug(f"Step {idx + 1} '{step.get('title')}': Major (duration > 30s)")

            # Check quality check
            if step.get("quality_check"):
                is_major = True
                logger.debug(f"Step {idx + 1} '{step.get('title')}': Major (quality check)")

            # Check if marked as important in title
            title = step.get("title", "").lower()
            if any(keyword in title for keyword in ["critical", "important", "verify", "inspect", "check"]):
                is_major = True
                logger.debug(f"Step {idx + 1} '{step.get('title')}': Major (critical keyword)")

            if is_major:
                major_indices.append(idx)

        if not major_indices:
            logger.warning("No major steps identified; all steps will be evaluated")
            # If no major steps found, treat all steps as major
            major_indices = list(range(len(steps)))

        return major_indices

    def _is_major_step(self, step_index: int) -> bool:
        """Check if a step is a major step"""
        if not self.focus_major_steps or self.major_step_indices is None:
            return True  # If not in major step mode, all steps are "major"
        return step_index in self.major_step_indices
