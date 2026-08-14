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

### Backend (Python 3.12.7)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # adjust if your Ollama host/models differ
```

`openai-whisper` also needs `ffmpeg` on your PATH:

```bash
# macOS
brew install ffmpeg tesseract
# Ubuntu/Debian
sudo apt-get install ffmpeg tesseract-ocr
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

```bash
cd backend
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

