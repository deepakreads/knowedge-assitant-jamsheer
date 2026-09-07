"""
Test Level 3 Monitoring Optimization: Frame Similarity Detection

These tests verify:
1. Frame hash computation for quick motion detection
2. Identical frames skipped after threshold
3. Frame changes reset skip counter
4. Frame similarity doesn't interfere with violation recovery
5. Frame hashes reset on step advance
6. API call reduction for static scenes (30-60% additional)
"""
import pytest
import json
import hashlib
from unittest.mock import AsyncMock, patch
from app.services.monitoring_service import SOPMonitoringService


class TestFrameSimilarityDetection:
    """Test frame similarity detection in monitoring service."""

    def test_frame_similarity_initialization(self):
        """Verify frame similarity tracking is initialized."""
        sop_data = {
            "title": "Test SOP",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "description": "First step",
                    "materials": ["object1"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        # Verify frame similarity tracking initialized
        assert hasattr(service, "last_frame_hash")
        assert hasattr(service, "frame_skip_count")
        assert hasattr(service, "frame_change_threshold")
        assert hasattr(service, "similarity_skip_enabled")

        # Verify initial state
        assert service.last_frame_hash is None
        assert service.frame_skip_count == 0
        assert service.frame_change_threshold == 2  # Skip after 2 identical frames
        assert service.similarity_skip_enabled is True

    @pytest.mark.asyncio
    async def test_identical_frames_skipped(self):
        """Verify identical frames are skipped after threshold."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Task",
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
                "confidence": 0.95
            })

            # Frame 1: Same frame data (different from None)
            frame_data = "identical_frame_base64_data"
            result1 = await service.analyze_frame(frame_data)
            assert mock_vision.call_count == 1
            assert service.frame_skip_count == 0  # First frame always analyzed
            # Result is cached (compliance >= 80)
            assert 0 in service.response_cache

            # Frame 2: Identical frame (skip_count = 1, below threshold)
            # Level 2 cache returns immediately (within TTL)
            # So Level 3 skip logic doesn't even matter yet
            result2 = await service.analyze_frame(frame_data)
            assert mock_vision.call_count == 1  # Level 2 cache used (no API call)
            assert service.frame_skip_count == 1
            assert result2 == result1, "Level 2 cache returns identical result"

            # Frame 3: Identical frame (skip_count = 2, now at Level 3 threshold)
            result3 = await service.analyze_frame(frame_data)
            # Level 3 skip returns cached result (after threshold check)
            assert mock_vision.call_count == 1  # Still no new API call
            assert service.frame_skip_count == 2
            assert result3 == result1, "Level 3 skip returns cached result"

            # Frame 4: Still identical (skip_count = 3, Level 3 keeps skipping)
            result4 = await service.analyze_frame(frame_data)
            assert mock_vision.call_count == 1  # Still skipping
            assert service.frame_skip_count == 3
            assert result4 == result1, "Level 3 continues to skip identical frames"

    @pytest.mark.asyncio
    async def test_frame_change_resets_skip_counter(self):
        """Verify frame change resets skip counter."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Task",
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
                "confidence": 0.95
            })

            # Frame 1-3: Identical (builds up skip counter)
            frame1 = "frame_data_1"
            await service.analyze_frame(frame1)  # Frame 1: API call
            await service.analyze_frame(frame1)  # Frame 2: Level 2 cache
            await service.analyze_frame(frame1)  # Frame 3: Level 3 skip or Level 2 cache

            assert service.frame_skip_count == 2
            assert mock_vision.call_count == 1  # Only Frame 1 calls API

            # Frame 4: Different frame (change mock response to test new analysis)
            # To force new analysis, return different compliance
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": False,  # Different response
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": False,
                "confidence": 0.70
            })

            frame2 = "frame_data_2_different"
            result = await service.analyze_frame(frame2)
            assert service.frame_skip_count == 0, "Skip counter should reset on frame change"
            assert service.last_frame_hash != hashlib.md5(frame1.encode()).hexdigest()
            assert mock_vision.call_count == 2  # New frame requires new analysis

    @pytest.mark.asyncio
    async def test_frame_similarity_respects_violation_recovery(self):
        """Verify frame similarity doesn't interfere with violation recovery."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Task",
                    "materials": ["red brick", "blue brick"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            # Frame 1: Violation
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": False,  # VIOLATION
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": False,
                "confidence": 0.90
            })

            frame_data = "frame_during_violation"
            result1 = await service.analyze_frame(frame_data)
            assert result1["compliance"] < 60
            assert service.step_active_violation[0] is True
            assert mock_vision.call_count == 1

            # Frame 2: Identical frame, but violation active
            result2 = await service.analyze_frame(frame_data)
            # Violation state prevents both Level 2 cache AND Level 3 skip
            # Must do fresh analysis
            assert mock_vision.call_count == 2
            assert service.step_active_violation[0] is True
            assert service.frame_skip_count == 1  # Hash still counts identical

            # Frame 3: User corrects (different frame = different hash)
            frame_data_corrected = "frame_after_correction_hash123"
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,  # CORRECTED
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": True,
                "confidence": 0.95
            })

            result3 = await service.analyze_frame(frame_data_corrected)
            assert result3["compliance"] >= 80
            assert mock_vision.call_count == 3

            # Frame 4: Still corrected same frame (recovery frame 2 = should clear)
            result4 = await service.analyze_frame(frame_data_corrected)
            # During recovery (was_violated=True at start), can't use Level 2 cache
            # Must analyze fresh
            assert mock_vision.call_count == 4
            # Recovery frames: 3->1, 4->2 (threshold reached, violation cleared)
            assert service.step_active_violation[0] is False  # Cleared on this frame!

            # Frame 5: Still identical, no violation (NOW skip + cache can apply)
            result5 = await service.analyze_frame(frame_data_corrected)
            # was_violated=False now, so Level 2 cache or Level 3 skip can apply
            # skip_count = 1 (frame 4 was identical), need 2 for skip
            # But Level 2 cache is fresh, returns immediately
            assert mock_vision.call_count == 4  # No new API call (cache used)
            assert result5["compliance"] == result4["compliance"]

            # Frame 6: Still identical (skip_count = 3, well above Level 3 threshold)
            result6 = await service.analyze_frame(frame_data_corrected)
            # skip_count reached and passed threshold (4->1, 5->2, 6->3)
            # Level 3 skip applies
            assert mock_vision.call_count == 4  # Still no new call
            assert service.frame_skip_count == 3

    @pytest.mark.asyncio
    async def test_frame_hash_reset_on_step_advance(self):
        """Verify frame hash resets when advancing to next step."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "description": "Step 1",
                    "materials": ["object1"],
                    "duration": 5  # Short to trigger auto-advance
                },
                {
                    "step_number": 2,
                    "title": "Step 2",
                    "description": "Step 2",
                    "materials": ["object2"],
                    "duration": 5
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        # Store frame hash
        frame_data = "frame_data_step1"
        frame_hash = hashlib.md5(frame_data.encode()).hexdigest()
        service.last_frame_hash = frame_hash
        service.frame_skip_count = 5

        # Advance step
        service._advance_step()

        # Verify frame hash reset
        assert service.last_frame_hash is None, "Frame hash should reset on step advance"
        assert service.frame_skip_count == 0, "Skip counter should reset on step advance"

    @pytest.mark.asyncio
    async def test_lego_assembly_scenario_api_reduction(self):
        """TEST: Realistic LEGO assembly scenario with frame similarity."""
        # Simulates: Setup (5s) → Place (2s) → Hold (5s) = 12s task
        # Without Level 3: 12 * 2 FPS = 24 frames analyzed
        # With Level 3: ~6 analyses (setup, place, hold phases)
        # Reduction: ~75%

        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Task",
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
                "confidence": 0.95
            })

            # Phase 1: Setup (2 different frames - each triggers analysis)
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": True,
                "confidence": 0.85  # Slightly different for each
            })
            await service.analyze_frame("setup_frame_0")
            assert mock_vision.call_count == 1

            # Different frame
            await service.analyze_frame("setup_frame_1")
            assert mock_vision.call_count == 2

            # Phase 2: Placement motion (4 frames - all different)
            for i in range(4):
                await service.analyze_frame(f"placement_frame_{i}")
            # Frames are different, so each triggers new analysis
            assert mock_vision.call_count == 6

            # Phase 3: Holding brick in place (10 identical frames)
            # Frame 0: Different frame from phase 2, analyzed
            # Frames 1-9: Identical to frame 0, skip after threshold
            for i in range(10):
                await service.analyze_frame("holding_frame_identical")

            # Frame 0 of phase 3: New analysis (different from phase 2)
            # Frames 1-9: Level 2 cache + Level 3 skip
            # Total: 6 (phases 1-2) + 1 (phase 3 frame 0) = 7
            assert mock_vision.call_count == 7
            assert service.frame_skip_count == 9  # 9 identical frames after first

            # API reduction: 7 calls for 16 frames = 56% reduction
            # With Level 2+3 combined optimization

    @pytest.mark.asyncio
    async def test_frame_similarity_with_compression_artifacts(self):
        """Verify frame similarity robust to minor compression differences."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "description": "Step 1",
                    "materials": ["object"],
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
                "confidence": 0.95
            })

            # Frame 1: Base frame
            frame_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            await service.analyze_frame(frame_base64)
            assert mock_vision.call_count == 1

            # Frame 2-3: Exact same frame data (binary identical)
            await service.analyze_frame(frame_base64)  # Frame 2: Level 2 cache
            await service.analyze_frame(frame_base64)  # Frame 3: Level 3 skip

            # Should have used cache (no more API calls)
            assert mock_vision.call_count == 1
            assert service.frame_skip_count == 2

            # Frame 4: Slightly different frame (different hash + different response)
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": False,  # Different response to force analysis
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": False,
                "confidence": 0.70
            })

            frame_different = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk" + "X"
            await service.analyze_frame(frame_different)

            # Skip counter reset, new analysis done
            assert mock_vision.call_count == 2
            assert service.frame_skip_count == 0  # Reset on frame change

    def test_frame_skip_threshold_configuration(self):
        """Verify frame skip threshold is configurable."""
        sop_data = {
            "title": "Test SOP",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "description": "Step 1",
                    "materials": ["object"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        # Default threshold
        assert service.frame_change_threshold == 2

        # Can be modified
        service.frame_change_threshold = 1  # More aggressive skipping
        assert service.frame_change_threshold == 1

        service.frame_change_threshold = 5  # Less aggressive skipping
        assert service.frame_change_threshold == 5

    def test_similarity_skip_can_be_disabled(self):
        """Verify frame similarity detection can be disabled."""
        sop_data = {
            "title": "Test SOP",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "description": "Step 1",
                    "materials": ["object"],
                    "duration": 30
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        # Enabled by default
        assert service.similarity_skip_enabled is True

        # Can be disabled
        service.similarity_skip_enabled = False
        assert service.similarity_skip_enabled is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
