import base64
import gc
import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image

from app.config import (
    OLLAMA_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_MAX_RETRIES,
    OLLAMA_TIMEOUT_SECONDS,
    VISION_IMAGE_MAX_DIM,
)

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when Ollama cannot be reached or returns an unusable response."""


def _client(timeout: float = OLLAMA_TIMEOUT_SECONDS) -> httpx.Client:
    """Initializes an HTTP client configured with Bearer token authorization for Ollama Cloud."""
    headers = {}
    api_key = OLLAMA_API_KEY or os.getenv("OLLAMA_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return httpx.Client(base_url=OLLAMA_BASE_URL, headers=headers, timeout=timeout)


def _encode_and_resize_image(image_path: str, max_dim: int = VISION_IMAGE_MAX_DIM) -> str:
    """
    Opens an image, downscales it so max(width, height) <= max_dim (384px),
    and returns a base64 JPEG string. Reduces payload transfer size and processing time.
    """
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / float(max(w, h))
                new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as exc:
        logger.warning("Image resize failed for %s, reading raw file: %s", image_path, exc)
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


def _error_body(exc: httpx.HTTPStatusError) -> str:
    try:
        return exc.response.text[:500]
    except Exception:
        return ""


def generate(
    model: str,
    prompt: str,
    images: Optional[List[str]] = None,
    system: Optional[str] = None,
    format_json: bool = False,
    options: Optional[Dict[str, Any]] = None,
    keep_alive: Optional[str] = None,
    timeout: float = OLLAMA_TIMEOUT_SECONDS,
) -> str:
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    if images:
        payload["images"] = [_encode_and_resize_image(p) for p in images]
    if format_json:
        payload["format"] = "json"
    if options:
        payload["options"] = options
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    last_exc: Optional[Exception] = None
    for attempt in range(OLLAMA_MAX_RETRIES + 1):
        try:
            with _client(timeout=timeout) as client:
                resp = client.post("/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "")
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.warning(
                "Ollama /api/generate attempt %d/%d failed (model=%s, status=%s): %s",
                attempt + 1,
                OLLAMA_MAX_RETRIES + 1,
                model,
                exc.response.status_code if exc.response is not None else "?",
                _error_body(exc),
            )
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.warning(
                "Ollama /api/generate attempt %d/%d failed (model=%s): %s",
                attempt + 1,
                OLLAMA_MAX_RETRIES + 1,
                model,
                exc,
            )
    raise OllamaError(f"Ollama /api/generate failed after retries: {last_exc}")


def chat(
    model: str,
    messages: List[Dict[str, Any]],
    format_json: bool = False,
    options: Optional[Dict[str, Any]] = None,
    keep_alive: Optional[str] = None,
    timeout: float = OLLAMA_TIMEOUT_SECONDS,
) -> str:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if format_json:
        payload["format"] = "json"
    if options:
        payload["options"] = options
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    last_exc: Optional[Exception] = None
    for attempt in range(OLLAMA_MAX_RETRIES + 1):
        try:
            with _client(timeout=timeout) as client:
                resp = client.post("/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.warning(
                "Ollama /api/chat attempt %d/%d failed (model=%s, status=%s): %s",
                attempt + 1,
                OLLAMA_MAX_RETRIES + 1,
                model,
                exc.response.status_code if exc.response is not None else "?",
                _error_body(exc),
            )
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.warning(
                "Ollama /api/chat attempt %d/%d failed (model=%s): %s",
                attempt + 1,
                OLLAMA_MAX_RETRIES + 1,
                model,
                exc,
            )
    raise OllamaError(f"Ollama /api/chat failed after retries: {last_exc}")


def embed(model: str, text: str) -> List[float]:
    payload = {"model": model, "input": text}
    try:
        with _client() as client:
            resp = client.post("/api/embed", json=payload)
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings")
            if embeddings:
                return embeddings[0]
            return data.get("embedding", [])
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise OllamaError(f"Ollama /api/embed failed: {exc}") from exc


def unload_model(model: str) -> None:
    try:
        with _client(timeout=10.0) as client:
            resp = client.post(
                "/api/generate",
                json={"model": model, "prompt": "", "keep_alive": 0},
            )
            resp.raise_for_status()
        logger.info("Successfully requested model unload for '%s'", model)
    except Exception as exc:
        logger.warning("Could not unload model '%s' (non-fatal): %s", model, exc)
    finally:
        gc.collect()


def extract_json(raw_text: str) -> Optional[Any]:
    if not raw_text:
        return None

    text = raw_text.strip()

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    logger.warning("Could not extract JSON from Ollama response: %.200s", raw_text)
    return None