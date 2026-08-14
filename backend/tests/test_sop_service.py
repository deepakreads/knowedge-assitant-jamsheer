from app.schemas.models import ActivityTimelineEntry
from app.services import ollama_service, sop_service


def _sample_timeline():
    return [
        ActivityTimelineEntry(
            step=1,
            start_time=0,
            end_time=15,
            activity="Prepare the component and required tools",
            visual_evidence=["Worker places the component on the workstation"],
            speech="Prepare the component and tools.",
            tools=["screwdriver"],
            materials=["component"],
            confidence=0.94,
        ),
        ActivityTimelineEntry(
            step=2,
            start_time=15,
            end_time=30,
            activity="Align the component",
            visual_evidence=["Worker aligns the component with mounting holes"],
            speech="Align the component with the mounting holes.",
            tools=[],
            materials=["component"],
            confidence=0.93,
        ),
    ]


def test_generate_sop_happy_path(monkeypatch):
    fake_response = """
    {
      "title": "Component Mounting Procedure",
      "purpose": "To mount the component correctly.",
      "scope": "Applies to the assembly workstation.",
      "required_tools": ["screwdriver"],
      "required_materials": ["component"],
      "safety": [],
      "steps": [
        {"step_number": 1, "title": "Prepare", "description": "Prepare the component and tools.", "tools": ["screwdriver"], "materials": ["component"], "safety_notes": [], "quality_check": null},
        {"step_number": 2, "title": "Align", "description": "Align the component with mounting holes.", "tools": [], "materials": ["component"], "safety_notes": [], "quality_check": null}
      ],
      "quality_checks": [],
      "estimated_duration": "30 sec"
    }
    """
    monkeypatch.setattr(ollama_service, "generate", lambda **kwargs: fake_response)

    sop = sop_service.generate_sop(
        job_id="job-123",
        video_filename="test.mp4",
        timeline=_sample_timeline(),
        title_hint="hint",
    )

    assert sop.status == "REVIEW_REQUIRED"
    assert sop.title == "Component Mounting Procedure"
    assert len(sop.steps) == 2
    assert sop.steps[0].step_number == 1
    assert sop.required_tools == ["screwdriver"]

    # Round-trips through disk.
    loaded = sop_service.load_sop(sop.id)
    assert loaded is not None
    assert loaded.id == sop.id


def test_generate_sop_falls_back_on_invalid_json(monkeypatch):
    monkeypatch.setattr(ollama_service, "generate", lambda **kwargs: "garbage, not json")

    sop = sop_service.generate_sop(
        job_id="job-456",
        video_filename="test.mp4",
        timeline=_sample_timeline(),
        title_hint="Fallback Title",
    )

    assert sop.status == "REVIEW_REQUIRED"
    assert sop.title == "Fallback Title"
    assert len(sop.steps) == 2
    assert sop.purpose == sop_service.NOT_SPECIFIED


def test_generate_sop_empty_timeline_raises():
    import pytest

    with pytest.raises(ValueError):
        sop_service.generate_sop(job_id="job-789", video_filename="test.mp4", timeline=[])
