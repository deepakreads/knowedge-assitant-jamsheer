# Video-to-SOP Knowledge Assistant (MVP)

Turns a manufacturing training video into a structured, human-reviewable
Standard Operating Procedure — by actually understanding what the worker
does, not just extracting on-screen text.

```
VIDEO → FRAMES → Qwen2.5-VL (visual) + Whisper (speech) + Tesseract (OCR)
      → ACTIVITY TIMELINE → Qwen2.5:7b → STRUCTURED SOP (Review Required)
```

Everything runs locally via [Ollama](https://ollama.com). No OpenAI, no
database, no vector search — this MVP stores job/SOP state as JSON files on
disk under `backend/data/`.

---

## 1. Files created

```
Knowledge-Assistant/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── main.py                          FastAPI entry point
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   ├── app/
│   │   ├── config.py                    env-driven settings
│   │   ├── routers/
│   │   │   ├── video_processing.py      upload + job status API
│   │   │   └── sop_generation.py        SOP generate/fetch API
│   │   ├── services/
│   │   │   ├── ollama_service.py        single reusable Ollama HTTP client
│   │   │   ├── job_store.py             JSON-file job persistence
│   │   │   ├── video_service.py         metadata + frame sampling + audio extraction (OpenCV/ffmpeg)
│   │   │   ├── vision_service.py        per-frame analysis via qwen2.5vl
│   │   │   ├── transcription_service.py Whisper speech-to-text
│   │   │   ├── ocr_service.py           Tesseract OCR
│   │   │   ├── activity_service.py      builds the activity timeline via qwen2.5:7b
│   │   │   ├── sop_service.py           SOP generation via qwen2.5:7b + persistence
│   │   │   └── pipeline_service.py      orchestrates the full pipeline as a background task
│   │   └── schemas/models.py            all Pydantic models (Job, Sop, ActivityTimelineEntry, ...)
│   ├── data/{uploads,frames,jobs,sops}/ JSON + media storage (created automatically)
│   └── tests/                           pytest suite, Ollama fully mocked
└── frontend/
    ├── app/
    │   ├── layout.tsx, page.tsx
    │   ├── upload/page.tsx              video upload form
    │   ├── processing/[jobId]/page.tsx  polls job status, shows staged progress
    │   └── sop/[id]/page.tsx            SOP review page
    ├── lib/api.ts                       typed API client
    ├── tailwind.config.ts, globals.css  visual identity
    └── Dockerfile
```

## 2. Installation commands

### Backend Setup

> **⚠️ Windows Users (No Admin Rights):** Due to Windows path length limitations (260 character limit), the virtual environment is created at a shorter path: `C:\dev\jamsheer-venv` instead of inside the project directory. This prevents `ModuleNotFoundError` when installing packages like PyTorch.

#### Option A: Windows Users (Recommended - Uses Shorter Path)

```powershell
# Navigate to the backend directory
cd backend

# Create virtual environment at shorter path (already done)
# If needed to recreate:
python -m venv C:\dev\jamsheer-venv

# Activate virtual environment
& "C:\dev\jamsheer-venv\Scripts\Activate.ps1"

# Install dependencies
pip install -r requirements.txt

# Copy environment config
copy .env.example .env
```

#### Option B: macOS/Linux or Windows (In-project venv)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
cp .env.example .env             # adjust if your Ollama host/models differ
```

### System Dependencies

`openai-whisper` requires system tools. Install based on your OS:

```bash
# macOS
brew install ffmpeg tesseract

# Ubuntu/Debian
sudo apt-get install ffmpeg tesseract-ocr

# Windows (using Chocolatey or direct install)
# - FFmpeg: https://ffmpeg.org/download.html
# - Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
```

### Frontend (Node 18+)

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

## 3. Ollama commands

Make sure Ollama is installed and running (`ollama serve`, or it's already a
background service), then pull the models this app uses:

```bash
ollama pull qwen2.5vl:latest
ollama pull qwen2.5:7b
ollama pull nomic-embed-text   # reserved for future semantic search, not required by this MVP
```

Verify Ollama is reachable:

```bash
curl http://localhost:11434/api/tags
```

## 4. Backend start command

### Windows Users (with Virtual Environment at C:\dev\jamsheer-venv)

**PowerShell:**
```powershell
# Activate the virtual environment first (REQUIRED!)
& "C:\dev\jamsheer-venv\Scripts\Activate.ps1"

# Navigate to backend
cd backend

# Run the app (choose one):
python main.py                  # Direct execution
# OR
uvicorn main:app --reload --host 0.0.0.0 --port 8000  # With auto-reload
```

**Quick Start Script (if available):**
```powershell
cd backend
.\run.ps1              # Uses default port 8000
.\run.ps1 -port 3000   # Custom port
```

### macOS/Linux

```bash
cd backend

# Activate virtual environment (if created with .venv)
source .venv/bin/activate

# Run the app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API is now at `http://localhost:8000` (interactive docs at `/docs`).

## 5. Frontend start command

```bash
cd frontend
npm run dev
```

The app is now at `http://localhost:3000`.

## 6. How to test with a video

1. Open `http://localhost:3000/upload`.
2. Drop in an MP4/AVI/MOV/MKV of a short manufacturing task (a phone
   recording of someone assembling something works fine for a smoke test).
3. You're redirected to `/processing/{jobId}`, which polls
   `GET /api/video-processing/jobs/{job_id}` every 3s and shows each stage:
   uploading → extracting frames → analyzing activities → transcribing →
   OCR → building timeline → generating SOP → completed.
4. On completion you're redirected to `/sop/{sopId}`, showing the full SOP:
   title, purpose, scope, tools, materials, safety, per-step timestamps,
   confidence, and quality checks. Status starts as `REVIEW_REQUIRED` —
   nothing is auto-approved.

You can also drive it directly with `curl`:

```bash
curl -X POST http://localhost:8000/api/video-processing/upload \
  -F "file=@/path/to/clip.mp4" -F "title=Bracket Assembly"

curl http://localhost:8000/api/video-processing/jobs/<job_id>
```

## 7. Running the backend tests

Ollama is fully mocked, so the suite runs without any AI models loaded:

```bash
cd backend
pytest -q
```

Covers: upload validation, the job-status API contract, the Ollama client's
retry/JSON-extraction logic, activity-timeline construction (including
fallback on invalid model JSON), and SOP generation (including fallback).

## 8. Important configuration notes

- **Frame sampling** scales with video length (`app/config.py`): ~1s
  intervals under a minute, ~2s under five minutes, ~3s beyond that, capped
  at `MAX_FRAMES_TO_ANALYZE` (default 120) so a long video never floods
  Ollama.
- **No hallucination guarantee**: the vision, activity, and SOP prompts all
  instruct the models to use `"unknown"` / `"Not specified in the source
  video."` rather than invent values, and the SOP service falls back to a
  deterministic, timeline-derived SOP if the LLM ever returns unusable JSON
  — so a bad model response degrades gracefully instead of hallucinating.
- **Resilience**: a failed frame is skipped (not fatal); a missing/failed
  audio track skips transcription only; a failed OCR pass skips OCR only.
  The job is only marked `error` if there's no visual evidence at all, or
  the timeline/SOP genuinely cannot be built.
- **API contract preserved**: `POST /api/video-processing/upload` and
  `GET /api/video-processing/jobs/{job_id}` return exactly the shapes
  specified in the project brief, including `sop_generated`, `sop_id`, and
  `sop_steps` once `status: "completed"`.
- Everything is file-based under `backend/data/` — safe to delete that
  folder to reset all state.

## 9. Elasticsearch Setup (Optional)

Elasticsearch is used for indexing and searching SOP documents. It's **optional** — the app works perfectly without it.

### For Local Development (No Security)

If using **standalone Elasticsearch** (not Docker), disable security for development:

**Edit:** `C:\elasticsearch-9.5.0\config\elasticsearch.yml`

Add or update these settings:

```yaml
xpack.security.enabled: false
xpack.security.enrollment.enabled: false
xpack.security.http.ssl:
  enabled: false
xpack.security.transport.ssl:
  enabled: false
```

Then restart Elasticsearch:

```powershell
cd C:\elasticsearch-9.5.0\bin
.\elasticsearch.bat
```

### Configuration in .env

```bash
# For local Elasticsearch (no credentials needed)
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_API_KEY=              # Leave empty for local dev
ELASTICSEARCH_SOP_INDEX=sops

# Or for Elasticsearch Cloud (requires API key)
ELASTICSEARCH_URL=https://your-cluster.es.us-central1.gcp.cloud.es.io:9243
ELASTICSEARCH_API_KEY=your_encoded_api_key
```

### If Elasticsearch is Not Available

The app automatically falls back to local storage:
- SOPs still generate and save locally
- No search indexing (but app works fine)
- Warning logged, non-critical

Leave `ELASTICSEARCH_URL` blank to skip Elasticsearch entirely:

```bash
ELASTICSEARCH_URL=        # App works without it
```

For detailed Elasticsearch setup, see:
- **[ELASTICSEARCH_STANDALONE_QUICK_START.md](ELASTICSEARCH_STANDALONE_QUICK_START.md)** - Quick setup guide
- **[ELASTICSEARCH_STANDALONE_SETUP.md](ELASTICSEARCH_STANDALONE_SETUP.md)** - Detailed setup
- **[ELASTICSEARCH_CONNECTION_FIXED.md](ELASTICSEARCH_CONNECTION_FIXED.md)** - Troubleshooting

## 10. Troubleshooting

### ModuleNotFoundError when running the app

**Problem:** `ModuleNotFoundError: No module named 'fastapi'` or similar

**Solution:** You must activate the virtual environment first:

```powershell
# Windows
& "C:\dev\jamsheer-venv\Scripts\Activate.ps1"

# macOS/Linux
source .venv/bin/activate
```

Verify it's activated by checking your prompt shows `(jamsheer-venv)` prefix.

### Windows path length error during installation

**Problem:** `[WinError 206] The filename or extension is too long`

**Root Cause:** Windows has a 260-character path limit. Deep project directories exceed this when installing large packages like PyTorch.

**Solution:** The virtual environment is created at `C:\dev\jamsheer-venv` (shorter path) instead of inside the project. This is intentional and required for Windows support without admin rights.

### Package import errors after activation

**Solution:** Verify you're using the correct Python:

```powershell
python -c "import sys; print(sys.prefix)"
# Should output: C:\dev\jamsheer-venv
```

If it shows a different path, the venv is not activated. Run activation command again.

### Port already in use

**Problem:** `Address already in use` when starting the backend

**Solution:** Use a different port:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Or kill the process using port 8000:

```powershell
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :8000
kill -9 <PID>
```

## 11. Key Files & Documentation

The backend directory includes these helpful guides:

### Setup & Build
- **[FIX_SUMMARY.md](backend/FIX_SUMMARY.md)** - Complete fix summary and setup details
- **[QUICK_START.md](backend/QUICK_START.md)** - Quick reference for running the app
- **[VENV_SETUP.md](backend/VENV_SETUP.md)** - Detailed virtual environment guide
- **[BUILD_COMPLETE.md](backend/BUILD_COMPLETE.md)** - Full build information
- **[run.ps1](backend/run.ps1)** - Automated startup script for Windows

### Elasticsearch Setup
- **[ELASTICSEARCH_STANDALONE_QUICK_START.md](ELASTICSEARCH_STANDALONE_QUICK_START.md)** - Quick 3-option setup guide
- **[ELASTICSEARCH_STANDALONE_SETUP.md](ELASTICSEARCH_STANDALONE_SETUP.md)** - Detailed Elasticsearch setup
- **[ELASTICSEARCH_CONNECTION_FIXED.md](ELASTICSEARCH_CONNECTION_FIXED.md)** - Connection troubleshooting
- **[NO_DOCKER_ELASTICSEARCH_SOLUTION.md](NO_DOCKER_ELASTICSEARCH_SOLUTION.md)** - Setup without Docker

### OCR & Special Features
- **[OCR_MIGRATION.md](backend/OCR_MIGRATION.md)** - Tesseract → EasyOCR migration
- **[TESSERACT_REPLACEMENT.md](backend/TESSERACT_REPLACEMENT.md)** - EasyOCR setup guide
- **[FIX_ELASTICSEARCH_CONNECTION.md](FIX_ELASTICSEARCH_CONNECTION.md)** - ES connection error fixes

