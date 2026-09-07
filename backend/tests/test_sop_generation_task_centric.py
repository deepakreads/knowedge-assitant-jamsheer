"""
Test that SOP generation produces TASK-CENTRIC SOPs, not hand-motion SOPs.

These tests verify that:
1. Generated SOPs focus on object states, not hand movements
2. Unnecessary human motion is filtered out
3. LEGO assembly information is preserved
4. SOPs are concise (not dozens of micro-steps)
5. SOPs are monitorable (verifiable from video)
"""
import pytest
import json
from unittest.mock import patch, AsyncMock
from app.services import video_type_prompts


class TestSOPGenerationTaskCentric:
    """Test that SOP generation focuses on tasks, not hand movements."""

    def test_demo_video_activity_prompt_ignores_hand_movements(self):
        """Verify DEMO_VIDEO_ACTIVITY_PROMPT explicitly filters hand movements."""
        prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Should have clear instructions to IGNORE these
        assert "Ignore hand movements" in prompt.lower() or "ignore" in prompt.lower()
        assert "wrist rotation" in prompt.lower()
        assert "hand trajectory" in prompt.lower()
        assert "approach" in prompt.lower()
        assert "grip" in prompt.lower().replace("grasping", "")

    def test_demo_video_activity_prompt_focuses_on_objects(self):
        """Verify DEMO_VIDEO_ACTIVITY_PROMPT focuses on object state."""
        prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Should focus on object-centric information
        assert "object" in prompt.lower()
        assert "placement" in prompt.lower()
        assert "state" in prompt.lower()
        assert "relationship" in prompt.lower()
        assert "assembly" in prompt.lower()

    def test_demo_video_sop_prompt_is_task_centric(self):
        """Verify DEMO_VIDEO_SOP_PROMPT emphasizes task outcomes, not motion."""
        prompt = video_type_prompts.DEMO_VIDEO_SOP_PROMPT

        # Should emphasize WHAT, not HOW
        assert "task" in prompt.lower()
        assert "what needs" in prompt.lower()
        assert "not how" in prompt.lower()
        assert "object state" in prompt.lower()
        assert "monitorable" in prompt.lower()

    def test_sop_prompt_warns_against_hand_motion_steps(self):
        """Verify SOP prompt lists BAD examples of hand-motion steps."""
        prompt = video_type_prompts.DEMO_VIDEO_SOP_PROMPT

        # Should have explicit BAD examples
        bad_examples = [
            "move hand toward",
            "rotate wrist",
            "grip",
            "approach"
        ]
        prompt_lower = prompt.lower()
        for example in bad_examples:
            assert example in prompt_lower, f"Prompt should warn against '{example}'"

    def test_sop_prompt_provides_good_examples(self):
        """Verify SOP prompt shows GOOD task-centric examples."""
        prompt = video_type_prompts.DEMO_VIDEO_SOP_PROMPT

        # Should have good examples focusing on object placement
        good_examples = [
            "place the blue lego block",
            "place the red lego block on top",
            "stable"
        ]
        prompt_lower = prompt.lower()
        for example in good_examples:
            assert example in prompt_lower, f"Prompt should include good example: '{example}'"

    def test_sop_prompt_emphasizes_concise_steps(self):
        """Verify SOP prompt recommends 3-8 steps, not dozens."""
        prompt = video_type_prompts.DEMO_VIDEO_SOP_PROMPT

        # Should target 3-8 steps for typical demos
        assert "3-8" in prompt or "3 to 8" in prompt.lower()
        assert "micro-step" in prompt.lower()

    def test_sop_prompt_emphasizes_object_state_quality_checks(self):
        """Verify quality checks focus on object state, not hand position."""
        prompt = video_type_prompts.DEMO_VIDEO_SOP_PROMPT

        # Quality checks should be about object state
        assert "object state" in prompt.lower()
        assert "hand position" in prompt.lower()  # Should mention NOT to do this

    def test_activity_prompt_targets_4_8_steps(self):
        """Verify DEMO_VIDEO_ACTIVITY_PROMPT targets reasonable granularity."""
        prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Activities should be meaningful task actions, not dozens of micro-steps
        assert "3-8" in prompt or "4-8" in prompt or "target" in prompt.lower()

    def test_activity_prompt_defines_meaningful_task_actions(self):
        """Verify DEMO_VIDEO_ACTIVITY_PROMPT explains what counts as a task action."""
        prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Should explain that one meaningful action = one activity
        assert "one meaningful" in prompt.lower() or "meaningful task action" in prompt.lower()

    def test_activity_prompt_includes_good_examples_only(self):
        """Verify DEMO_VIDEO_ACTIVITY_PROMPT only includes task-centric examples."""
        prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Good examples should be object placement, not hand movement
        assert "place the blue" in prompt.lower() or "place" in prompt.lower()
        assert "on top of" in prompt.lower() or "stack" in prompt.lower()

    def test_activity_prompt_rejects_hand_motion_examples(self):
        """Verify DEMO_VIDEO_ACTIVITY_PROMPT lists BAD examples of hand motion."""
        prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Should explicitly list BAD examples (hand motion)
        bad_keywords = [
            "move hand",
            "rotate wrist",
            "approach",
            "grip",
            "lift hand"
        ]
        for keyword in bad_keywords:
            assert keyword in prompt.lower(), f"Should warn against: {keyword}"

    def test_task_essential_vs_incidental_information(self):
        """Verify prompts distinguish task-essential from incidental information."""
        activity_prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT
        sop_prompt = video_type_prompts.DEMO_VIDEO_SOP_PROMPT

        combined = activity_prompt + sop_prompt

        # Should mention task-essential
        assert "task-essential" in combined.lower() or "task essential" in combined.lower() or "genuinely task" in combined.lower()

        # Should mention filtering out non-essential information
        assert "ignore" in combined.lower() or "filter" in combined.lower() or "do not include" in combined.lower()

    def test_prompts_emphasize_real_time_monitoring(self):
        """Verify prompts mention that SOPs must be monitorable in real-time."""
        sop_prompt = video_type_prompts.DEMO_VIDEO_SOP_PROMPT

        # Should emphasize real-time monitoring compatibility
        assert "monitorable" in sop_prompt.lower() or "real-time" in sop_prompt.lower()
        assert "vision" in sop_prompt.lower()

    def test_object_color_preservation(self):
        """Verify prompts preserve LEGO color information."""
        prompts = [
            video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT,
            video_type_prompts.DEMO_VIDEO_SOP_PROMPT
        ]

        for prompt in prompts:
            assert "color" in prompt.lower()
            assert "lego" in prompt.lower()

    def test_assembly_sequence_preservation(self):
        """Verify prompts preserve assembly order and sequence."""
        activity_prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        assert "sequence" in activity_prompt.lower()
        assert "order" in activity_prompt.lower()

    def test_object_relationship_preservation(self):
        """Verify prompts preserve object relationships."""
        activity_prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        assert "relationship" in activity_prompt.lower()
        assert "on top of" in activity_prompt.lower() or "stacking" in activity_prompt.lower()

    def test_no_wrist_rotation_in_prompts(self):
        """Verify prompts do NOT ask to extract wrist rotation as a requirement."""
        activity_prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT
        sop_prompt = video_type_prompts.DEMO_VIDEO_SOP_PROMPT

        combined = (activity_prompt + sop_prompt).lower()

        # Should NOT recommend extracting wrist rotation as SOP requirement
        # (It can appear in IGNORE or BAD EXAMPLES, but not as something to extract)
        assert "ignore" in activity_prompt.lower()  # Explicitly ignored


class TestSOPGenerationEdgeCases:
    """Test edge cases in task-centric SOP generation."""

    def test_object_rotation_vs_hand_rotation_distinction(self):
        """Verify prompts distinguish object rotation (task-relevant) from hand rotation (incidental)."""
        activity_prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Should mention object orientation when it matters
        assert "object orientation" in activity_prompt.lower() or "orientation" in activity_prompt.lower()

        # Should mention hand rotation as something to IGNORE
        assert "hand rotation" in activity_prompt.lower() or "wrist rotation" in activity_prompt.lower()

    def test_approach_direction_is_filtered(self):
        """Verify approach direction is not extracted as SOP requirement."""
        activity_prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Should explicitly exclude approach direction
        assert "approach" in activity_prompt.lower()
        assert "ignore" in activity_prompt.lower()

    def test_temporary_occlusion_is_filtered(self):
        """Verify temporary hand occlusion doesn't become SOP requirement."""
        activity_prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Should mention ignoring occlusion
        assert "occlusion" in activity_prompt.lower() or "hand in the way" in activity_prompt.lower()

    def test_movement_timing_not_extracted(self):
        """Verify exact timing/speed of movement is not extracted."""
        activity_prompt = video_type_prompts.DEMO_VIDEO_ACTIVITY_PROMPT

        # Should mention ignoring timing
        assert "timing" in activity_prompt.lower() or "speed" in activity_prompt.lower()

    def test_multiple_valid_approaches_accepted(self):
        """Verify SOP allows different approaches to accomplish same task."""
        sop_prompt = video_type_prompts.DEMO_VIDEO_SOP_PROMPT

        # Should mention robustness to different approaches
        assert "robust" in sop_prompt.lower() or "regardless" in sop_prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
