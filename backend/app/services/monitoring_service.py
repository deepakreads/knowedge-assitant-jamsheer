import time
import logging
import base64
import io
from typing import Dict, List, Optional
from PIL import Image

logger = logging.getLogger(__name__)


class SOPMonitoringService:
    """Real-time SOP compliance monitoring with vision-based analysis"""

    def __init__(self, sop: dict):
        """Initialize monitoring service for a specific SOP"""
        self.sop = sop
        self.current_step = 0
        self.step_start_time = time.time()
        self.compliance_history = []
        self.total_compliance = 0
        self.frames_analyzed = 0

        logger.info(f"Initialized monitoring for SOP: {sop.get('title', 'Unknown')}")

    async def analyze_frame(self, frame_base64: str) -> Dict:
        """
        Analyze current frame against current SOP step

        Returns:
            {
                "current_step": int,
                "total_steps": int,
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

            # Analyze the frame using vision AI
            compliance = await self._analyze_frame_with_vision(frame_base64, current_step)

            # Generate feedback
            feedback = self._generate_feedback(compliance, current_step)

            # Check if step should auto-advance
            step_complete = self._check_step_complete(current_step)
            if step_complete:
                self._advance_step()

            # Track compliance history
            self.compliance_history.append(compliance)
            self.frames_analyzed += 1
            self.total_compliance = sum(self.compliance_history) / len(self.compliance_history)

            # Calculate progress
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
        else:
            logger.info("All steps completed!")

    def _get_warnings(self, compliance: float, step: dict) -> List[str]:
        """Extract safety or procedural warnings"""
        warnings = []

        if compliance < 40:
            warnings.append("⚠️ Low compliance - check procedure")

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
        """
        try:
            from app.services import vision_service

            # Create vision prompt for this step
            tools_str = ", ".join(step.get("tools", [])) or "no specific tools"
            prompt = f"""Analyze this manufacturing/industrial work image and answer:

CURRENT SOP STEP: {step.get('title', 'Unknown')}
INSTRUCTIONS: {step.get('description', '')}
REQUIRED TOOLS: {tools_str}

Please answer:
1. What is the operator doing in this image?
2. What tools are visible?
3. Is the operator following the correct procedure for this step? (Yes/No/Partially)
4. Are all required tools visible and being used correctly?
5. Any safety concerns visible?
6. Overall, how well is this step being performed? (Percentage 0-100%)

Be very specific and base your assessment only on what you can see in the image."""

            # Send frame to vision service
            logger.info(f"Analyzing frame for step: {step.get('title', 'Unknown')}")
            analysis = await vision_service.analyze_frame_with_prompt(
                frame_base64,
                prompt
            )

            # Parse the analysis to calculate compliance
            compliance = self._parse_vision_analysis(analysis, step)
            logger.info(f"Frame compliance: {compliance}%")

            return compliance

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            # Fallback to time-based compliance if vision fails
            return self._calculate_compliance(step)

    def _parse_vision_analysis(self, analysis: str, step: dict) -> float:
        """
        Parse vision AI response and calculate compliance score.

        Scoring:
        - Following correct procedure: 50 points
        - Tools visible and correct: 30 points
        - No safety concerns: 20 points
        """
        score = 0
        analysis_lower = analysis.lower()

        # Check if following correct procedure (50 points)
        if "yes" in analysis_lower and ("correct" in analysis_lower or "proper" in analysis_lower):
            score += 50
        elif "partially" in analysis_lower:
            score += 25

        # Check for required tools (30 points)
        required_tools = step.get("tools", [])
        if required_tools:
            tools_found = sum(1 for tool in required_tools if tool.lower() in analysis_lower)
            if tools_found == len(required_tools):
                score += 30
            elif tools_found > 0:
                score += int(30 * (tools_found / len(required_tools)))
        else:
            score += 30  # No tools required

        # Check for safety concerns (20 points)
        if "unsafe" not in analysis_lower and "danger" not in analysis_lower and "safety" not in analysis_lower:
            score += 20

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
