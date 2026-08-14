"""
FastAPI entry point for the Video-to-SOP Knowledge Assistant backend.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_ORIGIN
from app.routers import sop_generation, video_processing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Video-to-SOP Knowledge Assistant",
    description=(
        "Converts manufacturing training videos into structured, "
        "review-required Standard Operating Procedures using local "
        "vision, speech and reasoning models via Ollama."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video_processing.router)
app.include_router(sop_generation.router)


@app.get("/")
async def root():
    return {"service": "video-to-sop-knowledge-assistant", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}
