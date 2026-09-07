"""
Regression tests for LEGO SOP false violation fix.

These tests verify that:
1. Hand movement variations do NOT cause violations
2. Wrong object state DOES cause violations
3. Task-essential requirements are checked
4. Incidental human motion is ignored
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.monitoring_service import SOPMonitoringService
from app.services import video_type_prompts


class TestDEMOVideoCompliancePrompts:
    """Test that DEMO_VIDEO (LEGO) prompts are task-centric."""

    def test_demo_video_compliance_prompt_ignores_hand_movements(self):
        """Verify DEMO_VIDEO compliance prompt explicitly ignores hand movements."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_SYSTEM_PROMPT
        assert "Ignore human hand movements" in prompt
        assert "wrist rotations" in prompt
        assert "grip styles" in prompt
        assert "Focus ONLY on object state" in prompt

    def test_demo_video_compliance_template_focuses_on_objects(self):
        """Verify DEMO_VIDEO template emphasizes object state."""
        template = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE
        assert "IGNORE" in template
        assert "Hand/wrist rotation" in template
        assert "Finger movements" in template
        assert "approach angle" in template
        assert "EVALUATE" in template
        assert "required_objects_present" in template
        assert "object_colors_correct" in template
        assert "object_positioning_correct" in template


class TestMonitoringServiceVideoTypeAwareness:
    """Test that monitoring service uses video-type-aware prompts."""

    @pytest.mark.asyncio
    async def test_analyze_frame_uses_demo_video_prompt_for_lego(self):
        """Verify LEGO SOPs use DEMO_VIDEO compliance prompts."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Take the red brick and place it on top of the blue brick.",
                    "tools": [],
                    "materials": ["red brick", "blue brick"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": True,
                "ignored_hand_movements": True,
                "confidence": 0.95
            })

            # Simulate a frame with hand rotation but correct object placement
            frame_base64 = "data:image/jpeg;base64,fake_data"
            result = await service.analyze_frame(frame_base64)

            # Verify the call was made with video-type-aware prompt
            mock_vision.assert_called_once()
            called_prompt = mock_vision.call_args[0][1]

            # Should use DEMO_VIDEO template for LEGO
            assert "required_objects_present" in called_prompt
            assert "object_colors_correct" in called_prompt
            assert "IGNORE" in called_prompt

    @pytest.mark.asyncio
    async def test_hand_rotation_does_not_cause_violation_for_demo_video(self):
        """TEST 1: Hand rotation with correct object state = PASS."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Take the red brick and place it on top of the blue brick.",
                    "tools": [],
                    "materials": ["red brick", "blue brick"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            # Vision analysis indicates:
            # - Objects are correct
            # - Hand rotated differently than reference
            # - This should NOT cause violation
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": True,
                "ignored_hand_movements": True,  # KEY: hand movements were ignored
                "compliance_explanation": "Red brick correctly placed on blue brick. Hand rotation ignored.",
                "confidence": 0.95
            })

            compliance = await service._analyze_frame_with_vision(
                "fake_frame_base64",
                sop_data["steps"][0]
            )

            # Hand rotation should not reduce compliance if objects are correct
            assert compliance >= 80, f"Compliance {compliance} too low; hand rotation should not cause violation"

    @pytest.mark.asyncio
    async def test_wrong_brick_color_causes_violation_for_demo_video(self):
        """TEST 2: Wrong object color = VIOLATION."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Take the red brick and place it on top of the blue brick.",
                    "tools": [],
                    "materials": ["red brick", "blue brick"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            # Vision analysis indicates:
            # - Wrong brick color (green instead of red)
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": False,  # KEY: colors wrong
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": False,
                "ignored_hand_movements": True,
                "compliance_explanation": "Green brick placed instead of red brick.",
                "confidence": 0.92
            })

            compliance = await service._analyze_frame_with_vision(
                "fake_frame_base64",
                sop_data["steps"][0]
            )

            # Wrong object should cause low compliance
            assert compliance < 60, f"Compliance {compliance} too high; wrong color should cause violation"

    @pytest.mark.asyncio
    async def test_wrong_placement_causes_violation_for_demo_video(self):
        """TEST 3: Wrong object placement (beside instead of on top) = VIOLATION."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Take the red brick and place it on top of the blue brick.",
                    "tools": [],
                    "materials": ["red brick", "blue brick"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            # Vision analysis indicates:
            # - Brick beside instead of on top
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": False,  # KEY: positioning wrong
                "object_orientation_correct": True,
                "task_compliant": False,
                "ignored_hand_movements": True,
                "compliance_explanation": "Red brick beside blue brick instead of on top.",
                "confidence": 0.90
            })

            compliance = await service._analyze_frame_with_vision(
                "fake_frame_base64",
                sop_data["steps"][0]
            )

            # Wrong placement should cause low compliance
            assert compliance < 60, f"Compliance {compliance} too high; wrong placement should cause violation"

    @pytest.mark.asyncio
    async def test_different_hand_trajectory_does_not_cause_violation(self):
        """TEST 4: Different hand trajectory but correct final state = PASS."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Approach from left, rotate wrist, place carefully.",
                    "tools": [],
                    "materials": ["red brick", "blue brick"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            # User approached from right (different from reference left approach)
            # But final object state is correct
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": True,
                "ignored_hand_movements": True,
                "compliance_explanation": "Red brick correctly placed. Approach angle ignored as not task-critical.",
                "confidence": 0.94
            })

            compliance = await service._analyze_frame_with_vision(
                "fake_frame_base64",
                sop_data["steps"][0]
            )

            # Different approach should not reduce compliance
            assert compliance >= 80, f"Compliance {compliance} too low; different approach angle should not cause violation"

    @pytest.mark.asyncio
    async def test_temporary_occlusion_does_not_cause_violation(self):
        """TEST 5: Hand temporarily blocks view but final state correct = PASS."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Take the red brick and place it on top of the blue brick.",
                    "tools": [],
                    "materials": ["red brick", "blue brick"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            # Hand was in the way, but final object state visible and correct
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": True,
                "ignored_hand_movements": True,
                "compliance_explanation": "Red brick correctly placed despite temporary hand occlusion.",
                "confidence": 0.88
            })

            compliance = await service._analyze_frame_with_vision(
                "fake_frame_base64",
                sop_data["steps"][0]
            )

            # Occlusion should not cause violation if final state is correct
            assert compliance >= 75, f"Compliance {compliance} too low; temporary occlusion should not cause violation"

    @pytest.mark.asyncio
    async def test_object_rotation_violation_when_required(self):
        """TEST 6: Required object rotation not met = VIOLATION."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Rotate brick 90 degrees and place",
                    "description": "Rotate the LEGO piece 90 degrees and place in slot.",
                    "tools": [],
                    "materials": ["LEGO brick"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            # Object placed but NOT rotated correctly
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": True,
                "object_orientation_correct": False,  # KEY: orientation wrong
                "task_compliant": False,
                "ignored_hand_movements": True,
                "compliance_explanation": "LEGO brick placed but not rotated to required 90 degree angle.",
                "confidence": 0.93
            })

            compliance = await service._analyze_frame_with_vision(
                "fake_frame_base64",
                sop_data["steps"][0]
            )

            # Wrong orientation should cause violation
            assert compliance < 60, f"Compliance {compliance} too high; wrong orientation should cause violation"


class TestParseVisionAnalysisNewFormat:
    """Test that _parse_vision_analysis correctly handles new JSON format."""

    def test_parse_demo_video_full_compliance(self):
        """Full DEMO_VIDEO compliance should score high."""
        service = SOPMonitoringService({"title": "Test", "steps": []}, focus_major_steps=False)

        analysis = json.dumps({
            "required_objects_present": True,
            "object_colors_correct": True,
            "object_positioning_correct": True,
            "object_orientation_correct": True,
            "task_compliant": True,
            "ignored_hand_movements": True,
            "confidence": 0.95
        })

        step = {"title": "Step 1", "materials": ["obj1"]}
        compliance = service._parse_vision_analysis(analysis, step, "object_state")

        assert compliance >= 90, f"Full compliance should score >= 90, got {compliance}"

    def test_parse_demo_video_missing_objects(self):
        """Missing required objects should score low."""
        service = SOPMonitoringService({"title": "Test", "steps": []}, focus_major_steps=False)

        analysis = json.dumps({
            "required_objects_present": False,
            "object_colors_correct": False,
            "object_positioning_correct": False,
            "object_orientation_correct": False,
            "task_compliant": False,
            "ignored_hand_movements": False,
            "confidence": 0.85
        })

        step = {"title": "Step 1", "materials": ["obj1"]}
        compliance = service._parse_vision_analysis(analysis, step, "object_state")

        assert compliance <= 20, f"Missing objects should score low, got {compliance}"

    def test_parse_machine_video_equipment_active(self):
        """Active MACHINE_VIDEO equipment should score high."""
        service = SOPMonitoringService({"title": "Test", "steps": []}, focus_major_steps=False)

        analysis = json.dumps({
            "equipment_present": True,
            "equipment_active": True,
            "parameters_correct": True,
            "material_state_correct": True,
            "process_compliant": True,
            "confidence": 0.95
        })

        step = {"title": "Step 1", "tools": ["equipment"]}
        compliance = service._parse_vision_analysis(analysis, step, "equipment_state")

        assert compliance >= 85, f"Active equipment should score high, got {compliance}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
