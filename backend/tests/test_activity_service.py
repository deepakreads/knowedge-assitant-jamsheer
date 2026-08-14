from app.schemas.models import VisionObservation
from app.services import activity_service, ollama_service


def _sample_observations():
    return [
        VisionObservation(
            timestamp=0.0,
            frame_path="frame_000.jpg",
            actions=["Worker places component on workstation"],
            objects=["component"],
            tools=[],
            confidence=0.9,
        ),
        VisionObservation(
            timestamp=5.0,
            frame_path="frame_001.jpg",
            actions=["Worker aligns component with mounting holes"],
            objects=["component", "mounting plate"],
            tools=["screwdriver"],
            confidence=0.88,
        ),
    ]


def test_build_activity_timeline_happy_path(monkeypatch):
    fake_response = """
    [
      {
        "start_time": 0,
        "end_time": 5,
        "activity": "Prepare the component",
        "visual_evidence": ["Worker places component on workstation"],
        "speech": "",
        "ocr": [],
        "tools": [],
        "materials": ["component"],
        "confidence": 0.9
      },
      {
        "start_time": 5,
        "end_time": 10,
        "activity": "Align the component",
        "visual_evidence": ["Worker aligns component with mounting holes"],
        "speech": "",
        "ocr": [],
        "tools": ["screwdriver"],
        "materials": ["component"],
        "confidence": 0.88
      }
    ]
    """
    monkeypatch.setattr(ollama_service, "generate", lambda **kwargs: fake_response)

    timeline = activity_service.build_activity_timeline(_sample_observations(), [], [])

    assert len(timeline) == 2
    assert timeline[0].step == 1
    assert timeline[0].activity == "Prepare the component"
    assert timeline[1].tools == ["screwdriver"]


def test_build_activity_timeline_falls_back_on_invalid_json(monkeypatch):
    monkeypatch.setattr(ollama_service, "generate", lambda **kwargs: "not valid json")

    timeline = activity_service.build_activity_timeline(_sample_observations(), [], [])

    # Falls back to one activity per vision observation.
    assert len(timeline) == 2
    assert timeline[0].activity == "Worker places component on workstation"


def test_build_activity_timeline_empty_observations_returns_empty():
    assert activity_service.build_activity_timeline([], [], []) == []
