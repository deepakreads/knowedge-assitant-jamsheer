import sys
from pathlib import Path

# Make `app` importable when running `pytest` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dirs(tmp_path, monkeypatch):
    """Redirect all data directories to a temp dir so tests never touch real data/."""
    from app import config

    for attr in ("UPLOADS_DIR", "FRAMES_DIR", "JOBS_DIR", "SOPS_DIR"):
        new_dir = tmp_path / attr.lower()
        new_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(config, attr, new_dir)

    # job_store and sop_service import JOBS_DIR/SOPS_DIR directly at module
    # load time, so patch their references too.
    from app.services import job_store, sop_service

    monkeypatch.setattr(job_store, "JOBS_DIR", config.JOBS_DIR)
    monkeypatch.setattr(sop_service, "SOPS_DIR", config.SOPS_DIR)
    yield
