"""
Video Type Analyzer Service

Pre-evaluation layer to classify videos as:
1. DEMO_VIDEO - Hand movements with simple objects (cuboids, household items, stationery)
2. MACHINE_INSTRUCTIONS - Industrial/manufacturing machine operations

This classification determines which prompts and processing approach to use.
"""

import logging
from typing import Dict, List
from enum import Enum

from app.schemas.models import VisionObservation
from app.services import ai_service
from app.config import VISION_MODEL

logger = logging.getLogger(__name__)


class VideoType(str, Enum):
    """Video type classifications"""
    DEMO_VIDEO = "DEMO_VIDEO"
    MACHINE_INSTRUCTIONS = "MACHINE_INSTRUCTIONS"
    UNKNOWN = "UNKNOWN"


VIDEO_TYPE_DETECTION_PROMPT = """Analyze these video frame observations and determine the video type.

OBSERVATIONS:
{observations}

Determine if this is:
1. DEMO_VIDEO: Hand movements with simple objects
   - Hands visible performing actions
   - Simple objects: cuboids, blocks, boxes, books, pens, staplers, etc.
   - Household or stationery items
   - No industrial equipment
   - Example: "demonstrating how to stack blocks" or "showing pen placement"

2. MACHINE_INSTRUCTIONS: Industrial/manufacturing operations
   - Machine tools, equipment, or industrial apparatus visible
   - No or minimal hand visibility
   - Complex industrial processes
   - Manufacturing or assembly operations
   - Example: "injection molding machine" or "CNC lathe operation"

Answer ONLY with:
TYPE: DEMO_VIDEO or MACHINE_INSTRUCTIONS
CONFIDENCE: 0.0-1.0
REASONING: One sentence explanation

Format:
TYPE: [DEMO_VIDEO or MACHINE_INSTRUCTIONS]
CONFIDENCE: [0.0-1.0]
REASONING: [explanation]"""


class VideoTypeAnalyzer:
    """Analyzes video frames to determine content type"""

    @staticmethod
    def analyze_video_type(vision_observations: List[VisionObservation]) -> Dict:
        """
        Analyze video observations to determine video type.

        Args:
            vision_observations: List of frame observations from vision analysis

        Returns:
            {
                "type": "DEMO_VIDEO" | "MACHINE_INSTRUCTIONS" | "UNKNOWN",
                "confidence": 0.0-1.0,
                "reasoning": "explanation",
                "frame_count": int,
                "key_indicators": ["indicator1", "indicator2", ...]
            }
        """
        try:
            if not vision_observations:
                logger.warning("No observations available for video type analysis")
                return {
                    "type": VideoType.UNKNOWN,
                    "confidence": 0.0,
                    "reasoning": "No frame observations available",
                    "frame_count": 0,
                    "key_indicators": []
                }

            # Extract key indicators from observations
            key_indicators = VideoTypeAnalyzer._extract_indicators(vision_observations)

            # Perform local heuristic analysis first
            local_type = VideoTypeAnalyzer._heuristic_classification(
                vision_observations, key_indicators
            )

            logger.info(f"Video type analysis: {local_type['type']} (confidence: {local_type['confidence']:.2f})")
            logger.info(f"Key indicators: {', '.join(key_indicators)}")

            return {
                "type": local_type["type"],
                "confidence": local_type["confidence"],
                "reasoning": local_type["reasoning"],
                "frame_count": len(vision_observations),
                "key_indicators": key_indicators
            }

        except Exception as e:
            logger.error(f"Video type analysis failed: {e}")
            return {
                "type": VideoType.UNKNOWN,
                "confidence": 0.0,
                "reasoning": f"Analysis failed: {str(e)}",
                "frame_count": len(vision_observations) if vision_observations else 0,
                "key_indicators": []
            }

    @staticmethod
    def _extract_indicators(observations: List[VisionObservation]) -> List[str]:
        """Extract key indicators from observations"""
        indicators = []
        demo_keywords = [
            "hand", "block", "cube", "cuboid", "box", "book", "pen", "pencil","stick", "plastic container",
            "children toys","stapler", "paper", "card", "dice", "toy", "simple", "stack"
        ]
        machine_keywords = [
            "machine", "mold", "injection", "cnc", "lathe", "press", "drill",
            "saw", "tool", "equipment", "industrial", "manufacturing", "weld",
            "hydraulic", "screw", "motor", "spindle", "fixture", "clamp"
        ]

        all_text = " ".join([
            str(obs.actions) + " " + str(obs.objects) + " " + str(obs.tools)
            for obs in observations
        ]).lower()

        demo_count = sum(1 for keyword in demo_keywords if keyword in all_text)
        machine_count = sum(1 for keyword in machine_keywords if keyword in all_text)

        if demo_count > 0:
            indicators.extend([kw for kw in demo_keywords if kw in all_text])

        if machine_count > 0:
            indicators.extend([kw for kw in machine_keywords if kw in all_text])
        logger.info(f"demo_count: "+str(demo_count))
        logger.info(f"machine_count: "+str(machine_count))
        return list(set(indicators))  # Remove duplicates

    @staticmethod
    def _heuristic_classification(
        observations: List[VisionObservation],
        indicators: List[str]
    ) -> Dict:
        """
        Classify video type based on heuristics.

        Heuristics:
        1. Machine keywords present → MACHINE_INSTRUCTIONS
        2. Demo keywords + hand visible → DEMO_VIDEO
        3. Simple objects + hand movements → DEMO_VIDEO
        4. Industrial equipment → MACHINE_INSTRUCTIONS
        """
        demo_keywords = {
            "hand", "block", "cube", "cuboid", "box", "book", "pen", "pencil","stick", "plastic container","children toys",
            "stapler", "paper", "card", "dice", "toy", "simple", "stack", "gesture"
        }
        machine_keywords = {
            "machine", "mold", "injection", "cnc", "lathe", "press", "drill",
            "saw", "equipment", "industrial", "manufacturing", "weld",
            "hydraulic", "screw", "motor", "spindle", "fixture", "clamp"
        }

        demo_indicators = [ind for ind in indicators if ind in demo_keywords]
        machine_indicators = [ind for ind in indicators if ind in machine_keywords]

        # Check for hand presence (demo indicator)
        has_hand = any(
            "hand" in str(obs.actions).lower() or "hand" in str(obs.objects).lower()
            for obs in observations
        )

        # Check for machine presence
        has_machine = any(
            keyword in str(obs.objects).lower() or keyword in str(obs.tools).lower()
            for obs in observations
            for keyword in machine_keywords
        )

        # Classification logic - Compare counts to determine type
        demo_count = len(demo_indicators)
        machine_count = len(machine_indicators)

        logger.info(f"Classification counts - Demo: {demo_count}, Machine: {machine_count}, Has hand: {has_hand}, Has machine: {has_machine}")

        # Primary: Compare indicator counts - whichever has more wins
        if demo_count > machine_count:
            confidence = min(1.0, 0.6 + (demo_count * 0.15))
            return {
                "type": VideoType.DEMO_VIDEO,
                "confidence": confidence,
                "reasoning": f"More demo indicators ({demo_count}) than machine indicators ({machine_count})"
            }

        elif machine_count > demo_count:
            confidence = min(1.0, 0.6 + (machine_count * 0.15))
            return {
                "type": VideoType.MACHINE_INSTRUCTIONS,
                "confidence": confidence,
                "reasoning": f"More machine indicators ({machine_count}) than demo indicators ({demo_count})"
            }

        # Secondary: If equal counts or one is zero, use presence indicators
        elif has_hand and demo_indicators:
            return {
                "type": VideoType.DEMO_VIDEO,
                "confidence": min(1.0, 0.6 + (demo_count * 0.15)),
                "reasoning": "Hand movements with simple objects detected"
            }

        elif has_machine and machine_indicators:
            return {
                "type": VideoType.MACHINE_INSTRUCTIONS,
                "confidence": min(1.0, 0.6 + (machine_count * 0.15)),
                "reasoning": "Industrial equipment or machine keywords detected"
            }

        elif has_hand:
            return {
                "type": VideoType.DEMO_VIDEO,
                "confidence": 0.5,
                "reasoning": "Hand movements detected, likely demo video"
            }

        elif has_machine:
            return {
                "type": VideoType.MACHINE_INSTRUCTIONS,
                "confidence": 0.5,
                "reasoning": "Machine equipment detected"
            }

        elif demo_indicators:
            return {
                "type": VideoType.DEMO_VIDEO,
                "confidence": 0.5,
                "reasoning": f"Simple objects detected: {', '.join(demo_indicators[:3])}"
            }

        else:
            return {
                "type": VideoType.UNKNOWN,
                "confidence": 0.0,
                "reasoning": "Insufficient evidence to classify video type"
            }

    @staticmethod
    def format_observations_for_analysis(observations: List[VisionObservation]) -> str:
        """Format observations for the analysis prompt"""
        lines = []
        for i, obs in enumerate(observations):
            lines.append(f"Frame {i+1} [t={obs.timestamp}s]:")
            if obs.actions:
                lines.append(f"  Actions: {', '.join(obs.actions)}")
            if obs.objects:
                lines.append(f"  Objects: {', '.join(obs.objects)}")
            if obs.tools:
                lines.append(f"  Tools: {', '.join(obs.tools)}")

        return "\n".join(lines)
