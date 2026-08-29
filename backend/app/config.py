import os
from pathlib import Path

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

UPLOADS_DIR = DATA_DIR / "uploads"
FRAMES_DIR = DATA_DIR / "frames"
JOBS_DIR = DATA_DIR / "jobs"
SOPS_DIR = DATA_DIR / "sops"

for directory in [UPLOADS_DIR, FRAMES_DIR, JOBS_DIR, SOPS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# CORS / Frontend settings
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# File constraints
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))

# Whisper Audio Model Settings
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")

# AICredits Configuration
AICREDITS_BASE_URL = os.getenv("AICREDITS_BASE_URL", "https://api.aicredits.in/v1")
AICREDITS_API_KEY = os.getenv("AICREDITS_API_KEY", "sk-live-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")


# AI Model Selection (Cheapest options selected)
VISION_MODEL = os.getenv("VISION_MODEL", "google/gemma-3-4b-it")          # ~$0.05 / 1M Input
SOP_MODEL = os.getenv("SOP_MODEL", "inclusionai/ling-2.6-flash")          # ~$0.01 / 1M Input

# Frame Analysis & Performance Tuning
MAX_FRAMES_TO_ANALYZE = int(os.getenv("MAX_FRAMES_TO_ANALYZE", "16"))    # Safe batch size under 60 RPM
VISION_IMAGE_MAX_DIM = int(os.getenv("VISION_IMAGE_MAX_DIM", "384"))      # Keeps image token cost low
MAX_CONCURRENT_VISION_WORKERS = int(os.getenv("MAX_CONCURRENT_VISION_WORKERS", "2")) # Safeguard against 429 concurrency cap

# API Rules
AICREDITS_TIMEOUT_SECONDS = float(os.getenv("AICREDITS_TIMEOUT_SECONDS", "120.0"))
AICREDITS_MAX_RETRIES = int(os.getenv("AICREDITS_MAX_RETRIES", "2"))

# OCR Configuration
# Using EasyOCR (pure Python) instead of Tesseract (requires external executable)
# EasyOCR is compatible with security policies that block executable downloads
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() in ("true", "1", "yes")


# --- Elasticsearch Configuration ---
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
ELASTICSEARCH_API_KEY = os.getenv("ELASTICSEARCH_API_KEY", None)
ELASTICSEARCH_SOP_INDEX = os.getenv("ELASTICSEARCH_SOP_INDEX", "sops")