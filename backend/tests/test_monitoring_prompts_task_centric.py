"""
Test that monitoring prompts are TASK-CENTRIC and STATE-FOCUSED.

These tests verify that:
1. Monitoring prompts ignore hand/operator movements
2. Monitoring prompts focus on object/process state
3. Monitoring prompts are robust to technique variations
4. Monitoring prompts provide clear examples
"""
import pytest
from app.services import video_type_prompts


class TestMonitoringPromptsTaskCentric:
    """Test that monitoring prompts focus on task/process state, not hand movements."""

    def test_demo_video_compliance_prompt_ignores_hand_movements(self):
        """Verify DEMO_VIDEO compliance prompt explicitly filters hand movements."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should have clear instructions to ignore these
        assert "ignore" in prompt.lower()
        assert "hand position" in prompt.lower() or "hand movement" in prompt.lower()
        assert "wrist" in prompt.lower()
        assert "grip" in prompt.lower()
        assert "approach" in prompt.lower()

    def test_demo_video_compliance_prompt_focuses_on_object_state(self):
        """Verify DEMO_VIDEO compliance prompt focuses on object state."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should focus on object state evaluation
        assert "object state" in prompt.lower()
        assert "correct position" in prompt.lower() or "positioning" in prompt.lower()
        assert "relationship" in prompt.lower()
        assert "final state" in prompt.lower()

    def test_demo_video_system_prompt_emphasizes_task_compliance(self):
        """Verify DEMO_VIDEO system prompt emphasizes evaluating final state."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_SYSTEM_PROMPT

        # Should emphasize task compliance evaluation
        assert "task" in prompt.lower()
        assert "object state" in prompt.lower()
        assert "ignore" in prompt.lower()
        assert "hand" in prompt.lower() or "movement" in prompt.lower()

    def test_demo_video_compliance_provides_examples(self):
        """Verify compliance prompt provides good/bad examples."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should have examples showing correct evaluation
        assert "example" in prompt.lower()
        assert "compliant" in prompt.lower() or "correct" in prompt.lower()

    def test_demo_video_examples_show_different_techniques_acceptable(self):
        """Verify examples show that different user techniques are OK."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should show that different approach/technique is acceptable
        assert "different" in prompt.lower()
        assert "technique" in prompt.lower() or "approach" in prompt.lower()
        assert "ignore" in prompt.lower()

    def test_machine_video_compliance_ignores_operator_movements(self):
        """Verify MACHINE_VIDEO compliance prompt ignores operator movements."""
        prompt = video_type_prompts.MACHINE_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should ignore operator movements
        assert "operator" in prompt.lower() or "body" in prompt.lower()
        assert "ignore" in prompt.lower()
        assert "movement" in prompt.lower()

    def test_machine_video_compliance_focuses_on_equipment_state(self):
        """Verify MACHINE_VIDEO compliance prompt focuses on equipment/process state."""
        prompt = video_type_prompts.MACHINE_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should focus on equipment state
        assert "equipment" in prompt.lower()
        assert "state" in prompt.lower()
        assert "parameter" in prompt.lower() or "reading" in prompt.lower()
        assert "process" in prompt.lower()

    def test_machine_video_system_prompt_emphasizes_process_compliance(self):
        """Verify MACHINE_VIDEO system prompt emphasizes process state."""
        prompt = video_type_prompts.MACHINE_VIDEO_COMPLIANCE_SYSTEM_PROMPT

        # Should focus on process compliance
        assert "process" in prompt.lower()
        assert "equipment" in prompt.lower()
        assert "operational state" in prompt.lower() or "state" in prompt.lower()

    def test_demo_video_compliance_decision_logic_clear(self):
        """Verify compliance prompt explains decision logic clearly."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should have clear decision logic
        assert "decision" in prompt.lower() or "logic" in prompt.lower()
        assert "compliant" in prompt.lower()

    def test_demo_video_compliance_distinguishes_object_vs_hand_rotation(self):
        """Verify compliance prompt distinguishes object rotation from hand rotation."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should evaluate object orientation
        assert "object orientation" in prompt.lower() or "orientation correct" in prompt.lower()
        # But ignore hand/wrist rotation
        assert "wrist" in prompt.lower()

    def test_compliance_prompts_emphasize_final_state(self):
        """Verify both compliance prompts emphasize final state over process."""
        demo_prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE
        machine_prompt = video_type_prompts.MACHINE_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should focus on final state
        assert "final" in demo_prompt.lower() or "final" in machine_prompt.lower()
        assert "state" in demo_prompt.lower() or "state" in machine_prompt.lower()

    def test_compliance_prompts_accept_technique_variation(self):
        """Verify compliance prompts accept different user techniques."""
        demo_prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE
        machine_prompt = video_type_prompts.MACHINE_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        combined = (demo_prompt + machine_prompt).lower()

        # Should mention accepting different techniques
        assert "different" in combined
        assert "technique" in combined or "variation" in combined

    def test_demo_video_compliance_clear_pass_fail_criteria(self):
        """Verify compliance prompt has clear pass/fail criteria."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should have decision logic
        assert "all required" in prompt.lower() and "present" in prompt.lower()
        assert "correct" in prompt.lower()

    def test_machine_video_compliance_clear_pass_fail_criteria(self):
        """Verify MACHINE_VIDEO has clear pass/fail criteria."""
        prompt = video_type_prompts.MACHINE_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should have decision logic
        assert "all required" in prompt.lower()
        assert "correct state" in prompt.lower() or "correct" in prompt.lower()

    def test_monitoring_examples_show_hand_position_ignored(self):
        """Verify examples show hand position is ignored for LEGO."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should have example showing hand position ignored
        assert "hand" in prompt.lower()
        assert "ignore" in prompt.lower()

    def test_monitoring_examples_show_wrong_position_caught(self):
        """Verify examples show wrong object positioning IS caught."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should show that wrong positioning is caught
        assert "beside" in prompt.lower() or "wrong position" in prompt.lower() or "non-compliant" in prompt.lower()

    def test_demo_compliance_json_response_clear(self):
        """Verify compliance prompt specifies clear JSON format."""
        prompt = video_type_prompts.DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should show JSON format
        assert "json" in prompt.lower()
        assert "required_objects_present" in prompt
        assert "task_compliant" in prompt

    def test_machine_compliance_json_response_clear(self):
        """Verify MACHINE_VIDEO compliance prompt specifies clear JSON format."""
        prompt = video_type_prompts.MACHINE_VIDEO_COMPLIANCE_PROMPT_TEMPLATE

        # Should show JSON format
        assert "json" in prompt.lower()
        assert "equipment_present" in prompt
        assert "process_compliant" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
