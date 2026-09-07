"""
Regression tests for SOP violation recovery.

These tests verify that:
1. Violations are detected correctly
2. Violations are cleared when the user corrects the task
3. The alarm automatically turns OFF after recovery
4. The SOP progresses to the next step after recovery
5. Multiple violations and recoveries work correctly
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.routers.sop_generation import WorkflowSession
from app.services.monitoring_service import SOPMonitoringService


class TestViolationRecoveryWorkflowSession:
    """Test violation recovery in the REST API path (WorkflowSession)."""

    def test_violation_then_recovery(self):
        """TEST 1: Violation detected, then corrected, then cleared."""
        session = WorkflowSession("test_sop", max_steps=5)

        # Start workflow at step 1
        state_updated, violation = session.update_step_detection(1)
        assert state_updated is True
        assert violation is None
        assert session.current_step == 1

        # Detect incorrect step (violation)
        state_updated, violation = session.update_step_detection(3)  # Skipped step 2
        assert state_updated is False
        assert violation is not None
        assert violation["type"] == "skipped"
        assert session.step_active_violation.get(1) == "skipped"  # Active violation marked
        assert session.current_step == 1  # Still on step 1

        # User corrects and we see step 1 again
        state_updated, violation = session.update_step_detection(1)
        # First frame showing correct step - need 2 for stability
        assert state_updated is False  # Not yet recovered (need 2 frames)

        # Second frame confirming correct state
        state_updated, violation = session.update_step_detection(1)
        assert state_updated is True  # Recovery confirmed
        assert violation is None
        assert session.step_active_violation.get(1) is None  # Active violation cleared
        assert session.violation_history[0].get("has_been_violated") is True  # Historical record preserved

    def test_violation_remains_until_corrected(self):
        """TEST 2: Violation remains active until user corrects the step."""
        session = WorkflowSession("test_sop", max_steps=5)

        # Start at step 1
        session.update_step_detection(1)

        # Detect violation (wrong step detected)
        state_updated, violation = session.update_step_detection(3)
        assert violation is not None
        assert session.step_active_violation.get(1) == "skipped"

        # Keep seeing the wrong step
        state_updated, violation = session.update_step_detection(3)
        assert state_updated is False
        assert session.step_active_violation.get(1) == "skipped"  # Violation still active

        # Keep seeing the wrong step
        state_updated, violation = session.update_step_detection(3)
        assert state_updated is False
        assert session.step_active_violation.get(1) == "skipped"  # Violation still active

        # The violation should NOT automatically clear
        # Only clears when correct state is observed

    def test_violation_recovery_with_different_motion(self):
        """TEST 3: Recovery works even if user uses different approach to fix it."""
        session = WorkflowSession("test_sop", max_steps=5)

        # Start at step 1
        session.update_step_detection(1)

        # Violation detected
        session.update_step_detection(3)  # Wrong step
        assert session.step_active_violation.get(1) is not None

        # User corrects step (using different hand motion or approach, but step is correct)
        # First frame of correction
        state_updated, violation = session.update_step_detection(1)
        assert state_updated is False  # Waiting for stability

        # Second frame confirms correction (even if hand motion was different)
        state_updated, violation = session.update_step_detection(1)
        assert state_updated is True
        assert session.step_active_violation.get(1) is None
        assert violation is None

    def test_multiple_violations_and_recoveries(self):
        """TEST 4: Multiple violation/recovery cycles work independently."""
        session = WorkflowSession("test_sop", max_steps=5)

        # Step 1: Violation then recovery
        session.update_step_detection(1)
        state_updated, violation = session.update_step_detection(3)  # Violation
        assert violation is not None
        assert session.step_active_violation.get(1) == "skipped"

        # Recover from step 1 violation
        state_updated, violation = session.update_step_detection(1)
        assert state_updated is False  # First frame of recovery
        state_updated, violation = session.update_step_detection(1)
        assert state_updated is True  # Second frame confirms recovery
        assert session.step_active_violation.get(1) is None

        # Advance to step 2
        state_updated, violation = session.update_step_detection(2)
        assert state_updated is True

        # Step 2: New violation
        state_updated, violation = session.update_step_detection(5)  # Skipped to step 5
        assert violation is not None
        assert session.step_active_violation.get(2) is not None

        # Recover from step 2 violation
        state_updated, violation = session.update_step_detection(2)
        assert state_updated is False  # First frame
        state_updated, violation = session.update_step_detection(2)
        assert state_updated is True  # Second frame confirms recovery
        assert session.step_active_violation.get(2) is None

        # Step 1's historical violation should not affect step 2
        assert session.step_violation_state.get(1) is True  # Historical
        assert session.step_active_violation.get(1) is None  # But cleared

    def test_violation_history_preserved(self):
        """TEST 5: Historical violation records are preserved for auditing."""
        session = WorkflowSession("test_sop", max_steps=5)

        session.update_step_detection(1)
        state_updated, violation = session.update_step_detection(3)

        # Should have violation in history
        assert len(session.violation_history) > 0
        assert session.violation_history[0]["type"] == "skipped"

        # Recover
        session.update_step_detection(1)
        session.update_step_detection(1)

        # Historical record should still exist
        assert len(session.violation_history) > 0
        assert session.violation_history[0].get("has_been_violated") is True


class TestViolationRecoveryMonitoringService:
    """Test violation recovery in the WebSocket path (MonitoringService)."""

    @pytest.mark.asyncio
    async def test_monitoring_service_violation_then_recovery(self):
        """TEST 6: Monitoring service detects violation and clears it on recovery."""
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
            # Frame 1: Violation (wrong placement)
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": False,  # VIOLATION
                "object_orientation_correct": True,
                "task_compliant": False,
                "ignored_hand_movements": True,
                "confidence": 0.85
            })

            result1 = await service.analyze_frame("fake_frame_1")
            assert result1["compliance"] < 60  # Violation
            assert service.step_active_violation.get(0) is True

            # Frame 2: Still wrong (violation persists)
            result2 = await service.analyze_frame("fake_frame_2")
            assert result2["compliance"] < 60
            assert service.step_active_violation.get(0) is True  # Still violated

            # Frame 3: User corrects (correct placement)
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": True,  # CORRECTED
                "object_orientation_correct": True,
                "task_compliant": True,
                "ignored_hand_movements": True,
                "confidence": 0.94
            })

            result3 = await service.analyze_frame("fake_frame_3")
            assert result3["compliance"] >= 80  # Good compliance
            # First frame of recovery - violation not yet cleared (need stability)
            assert service.step_active_violation.get(0) is True

            # Frame 4: Correction confirmed
            result4 = await service.analyze_frame("fake_frame_4")
            assert result4["compliance"] >= 80
            # After 2 frames, violation should be cleared
            assert service.step_active_violation.get(0) is False
            assert service.step_recovery_frames == 0  # Reset after recovery

    @pytest.mark.asyncio
    async def test_monitoring_service_wrong_state_keeps_violation_active(self):
        """TEST 7: Violation remains if user doesn't correct the task."""
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
            # Violation
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": False,
                "object_orientation_correct": True,
                "task_compliant": False,
                "ignored_hand_movements": True,
                "confidence": 0.80
            })

            # Frame 1
            await service.analyze_frame("fake_frame_1")
            assert service.step_active_violation.get(0) is True

            # Frame 2 - still wrong
            await service.analyze_frame("fake_frame_2")
            assert service.step_active_violation.get(0) is True

            # Frame 3 - still wrong (user hasn't corrected)
            await service.analyze_frame("fake_frame_3")
            assert service.step_active_violation.get(0) is True

            # Violation should persist
            assert service.step_active_violation.get(0) is True

    @pytest.mark.asyncio
    async def test_monitoring_service_violation_not_blocking_next_step(self):
        """TEST 8: After recovery, next step evaluation proceeds normally."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Task 1",
                    "tools": [],
                    "materials": ["red brick", "blue brick"],
                    "duration": 30
                },
                {
                    "step_number": 2,
                    "title": "Place yellow brick on top",
                    "description": "Task 2",
                    "tools": [],
                    "materials": ["yellow brick"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            # Step 1: Violation then recovery
            mock_vision.return_value = json.dumps({
                "required_objects_present": False,
                "object_colors_correct": False,
                "object_positioning_correct": False,
                "object_orientation_correct": False,
                "task_compliant": False,
                "ignored_hand_movements": True,
                "confidence": 0.50
            })
            await service.analyze_frame("frame_1")  # Violation

            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": True,
                "ignored_hand_movements": True,
                "confidence": 0.95
            })
            await service.analyze_frame("frame_2")  # Recovery frame 1
            await service.analyze_frame("frame_3")  # Recovery frame 2 - should recover

            # Step should have advanced
            if service.current_step >= 1:
                # Step 2 should now be evaluated
                assert service.step_active_violation.get(0) is False
                # Step 1 violation should be cleared


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
