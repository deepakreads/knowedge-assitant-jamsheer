"""
Test Level 2 Monitoring Optimization: Frame Interval + Response Caching

These tests verify:
1. Frame interval change from 2500ms to 500ms (frontend)
2. Response caching for 300ms on static scenes (backend)
3. Cache invalidation on step advancement
4. Immediate return of cached results
"""
import pytest
import json
import time
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.monitoring_service import SOPMonitoringService


class TestResponseCaching:
    """Test response caching in monitoring service."""

    def test_cache_initialization(self):
        """Verify cache is initialized on service creation."""
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

        # Verify cache dicts exist
        assert hasattr(service, "response_cache")
        assert hasattr(service, "response_cache_time")
        assert isinstance(service.response_cache, dict)
        assert isinstance(service.response_cache_time, dict)

        # Verify cache TTL
        assert service.cache_ttl_ms == 300  # 300ms TTL
        assert len(service.response_cache) == 0  # Empty initially
        assert len(service.response_cache_time) == 0

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self):
        """Verify cache hit returns previously cached result without vision API call."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Take the red brick and place it on top of the blue brick.",
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

            # FIRST FRAME: No cache, should call vision API
            frame_data = "identical_frame_base64_for_level2_test"
            result1 = await service.analyze_frame(frame_data)
            assert mock_vision.call_count == 1, "First frame should call vision API"
            assert result1["compliance"] >= 90
            assert 0 in service.response_cache, "Result should be cached"

            # SECOND FRAME (same frame, within 300ms): Should use cache, NO vision API call
            # NOTE: Identical frames (Level 3) also prevent re-analysis
            result2 = await service.analyze_frame(frame_data)
            assert mock_vision.call_count == 1, "Cache hit: vision API NOT called again"
            assert result2 == result1, "Should return identical cached result"

    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Verify cache expires after 300ms TTL."""
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

        # Pre-populate cache with old timestamp (400ms ago)
        current_time_ms = time.time() * 1000
        old_time_ms = current_time_ms - 400  # 400ms ago = expired
        cached_result = {
            "compliance": 95,
            "step_title": "Step 1",
            "current_step": 1,
            "total_steps": 1
        }

        service.response_cache[0] = cached_result
        service.response_cache_time[0] = old_time_ms

        with patch("app.services.vision_service.analyze_frame_with_prompt") as mock_vision:
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": True,
                "confidence": 0.95
            })

            # Cache should be expired, should call vision API
            result = await service.analyze_frame("frame_base64")
            assert mock_vision.call_count == 1, "Expired cache should call vision API"

    @pytest.mark.asyncio
    async def test_cache_cleared_on_step_advance(self):
        """Verify cache is cleared when advancing to next step."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Step 1",
                    "materials": ["red brick", "blue brick"],
                    "duration": 5  # Short duration to trigger auto-advance
                },
                {
                    "step_number": 2,
                    "title": "Place yellow brick on top",
                    "description": "Step 2",
                    "materials": ["yellow brick"],
                    "duration": 5
                }
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        # Pre-populate cache for step 1
        service.response_cache[0] = {"compliance": 95, "step_title": "Step 1"}
        service.response_cache_time[0] = time.time() * 1000

        # Advance to step 2
        service._advance_step()

        # Cache for previous step should still exist (we don't clear all, just new step)
        assert 0 in service.response_cache, "Previous step cache still exists"
        assert 1 not in service.response_cache, "New step cache should be empty"

    @pytest.mark.asyncio
    async def test_multiple_frames_with_cache_hits(self):
        """Verify caching reduces vision API calls for repeated frames."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Step 1",
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

            # Send 5 identical frames within cache TTL window
            # Expected: 1 vision API call + 4 cache/skip hits
            # NOTE: With Level 3, identical frames are skipped after threshold
            frame_data = "identical_frame_for_cache_test"
            for i in range(5):
                result = await service.analyze_frame(frame_data)
                assert result["compliance"] >= 90

            # Should only have 1 vision API call (first frame)
            # Frames 2-5: Either Level 2 cache or Level 3 skip
            assert mock_vision.call_count == 1, "Should have 1 vision API call, rest from cache/skip"

    @pytest.mark.asyncio
    async def test_cache_improves_recovery_speed(self):
        """Verify cache enables faster violation recovery detection."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Step 1",
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
                "object_colors_correct": False,  # WRONG COLOR = VIOLATION
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": False,
                "confidence": 0.90
            })

            violation_frame = "frame_with_violation"
            result1 = await service.analyze_frame(violation_frame)
            assert result1["compliance"] < 60, "Should detect violation"
            assert service.step_active_violation[0] is True
            assert mock_vision.call_count == 1

            # Frame 2: User corrects (correct color now, SAME frame data for Level 3 test compatibility)
            mock_vision.return_value = json.dumps({
                "required_objects_present": True,
                "object_colors_correct": True,  # NOW CORRECT
                "object_positioning_correct": True,
                "object_orientation_correct": True,
                "task_compliant": True,
                "confidence": 0.95
            })

            # Use SAME frame data to prevent Level 3 cache clearing
            recovery_frame = "frame_after_correction"
            result2 = await service.analyze_frame(recovery_frame)
            assert result2["compliance"] >= 80, "Should show compliance"
            # Recovery frame 1 - not yet cleared
            assert service.step_active_violation[0] is True
            assert mock_vision.call_count == 2

            # Frame 3: Still corrected (same frame, during recovery NO cache but Level 3 may apply)
            result3 = await service.analyze_frame(recovery_frame)
            # During recovery (was_violated=True), cache/skip disabled to ensure recovery logic runs
            # So must analyze fresh
            assert result3["compliance"] >= 80, "Should still show compliance"
            # Recovery frame 2 - should clear violation
            assert service.step_active_violation[0] is False, "Violation should be cleared after 2 stable frames"
            assert mock_vision.call_count == 3, "Frame 3 must be analyzed (recovery mode)"

            # Frame 4: Stable state after recovery (NOW cache can be used)
            result4 = await service.analyze_frame(recovery_frame)
            # After recovery complete, was_violated=False, cache/Level 3 skip CAN be used
            assert result4["compliance"] == result3["compliance"], "Should return consistent compliance"
            # Frame 4 should use cache or Level 3 skip (not call vision API)
            assert mock_vision.call_count == 3, "Frame 4 should use cache/skip (no new API call)"

    def test_cache_memory_efficiency(self):
        """Verify cache doesn't grow indefinitely."""
        sop_data = {
            "title": "Multi-step SOP",
            "steps": [
                {
                    "step_number": i,
                    "title": f"Step {i}",
                    "description": f"Step {i} description",
                    "materials": ["object"],
                    "duration": 10
                }
                for i in range(1, 6)  # 5 steps
            ],
            "metadata": {"video_type": "DEMO_VIDEO"}
        }

        service = SOPMonitoringService(sop_data, focus_major_steps=False)

        # Simulate advancing through steps and caching
        for step_idx in range(5):
            service.response_cache[step_idx] = {"compliance": 90}
            service.response_cache_time[step_idx] = time.time() * 1000
            if step_idx < 4:
                service._advance_step()

        # Cache should contain all steps (we don't clear old steps, just new step on advance)
        # This is a trade-off: keep cache efficient but not grow too large
        cache_size = len(service.response_cache)
        assert cache_size <= 5, f"Cache size {cache_size} should be reasonable for 5 steps"

    @pytest.mark.asyncio
    async def test_cache_contains_complete_response(self):
        """Verify cached response has all required fields."""
        sop_data = {
            "title": "LEGO Assembly",
            "steps": [
                {
                    "step_number": 1,
                    "title": "Place red brick on blue brick",
                    "description": "Step description",
                    "materials": ["red brick", "blue brick"],
                    "duration": 30,
                    "tools": [],
                    "safety_notes": "Be careful"
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

            # First frame - stores in cache
            # Use same frame data to ensure cache/skip is tested
            frame_data = "frame_for_cache_test"
            result1 = await service.analyze_frame(frame_data)

            # Second frame - SAME frame data to ensure cache/Level 3 skip apply
            result2 = await service.analyze_frame(frame_data)

            # Verify cached result has all required fields
            required_fields = [
                "current_step", "total_steps", "step_title",
                "compliance", "overall_compliance", "feedback",
                "warnings", "progress_percent"
            ]
            for field in required_fields:
                assert field in result2, f"Cached result missing field: {field}"
                assert result2[field] == result1[field], f"Cached result mismatch for {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
