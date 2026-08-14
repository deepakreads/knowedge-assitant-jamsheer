import io

from fastapi.testclient import TestClient

from app.schemas.models import Job, JobStage, JobStatus
from app.services import job_store


def _make_client(monkeypatch):
    # Prevent the real background pipeline (which needs Ollama/ffmpeg/etc.)
    # from running during API tests.
    from app.routers import video_processing

    monkeypatch.setattr(video_processing, "run_pipeline", lambda job_id: None)

    from main import app

    return TestClient(app)


def test_upload_rejects_bad_extension(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.post(
        "/api/video-processing/upload",
        files={"file": ("not_a_video.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


def test_upload_creates_job(monkeypatch):
    client = _make_client(monkeypatch)
    fake_video = io.BytesIO(b"\x00\x00\x00\x18ftypmp42fake video bytes")
    response = client.post(
        "/api/video-processing/upload",
        files={"file": ("clip.mp4", fake_video, "video/mp4")},
        data={"title": "Test Video", "description": "A test"},
    )
    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "processing"
    assert body["progress"] == 0

    job = job_store.load_job(body["job_id"])
    assert job is not None
    assert job.title == "Test Video"


def test_job_status_not_found(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.get("/api/video-processing/jobs/does-not-exist")
    assert response.status_code == 404


def test_job_status_completed_contract(monkeypatch):
    client = _make_client(monkeypatch)

    job = Job(
        job_id="job-completed",
        status=JobStatus.COMPLETED,
        stage=JobStage.COMPLETED,
        progress=100,
        video_filename="clip.mp4",
        video_path="/tmp/clip.mp4",
        sop_id=None,
    )
    job_store.save_job(job)

    response = client.get("/api/video-processing/jobs/job-completed")
    assert response.status_code == 200
    body = response.json()
    # Contract required by the frontend/spec.
    assert body["status"] == "completed"
    assert body["sop_generated"] is False
    assert "sop_id" in body
    assert "sop_steps" in body
    assert body["progress"] == 100
