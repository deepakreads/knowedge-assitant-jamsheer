import base64
import gc
import io
import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI
from PIL import Image

from app.config import (
    AICREDITS_API_KEY,
    AICREDITS_BASE_URL,
    AICREDITS_MAX_RETRIES,
    AICREDITS_TIMEOUT_SECONDS,
    VISION_IMAGE_MAX_DIM,
)

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Raised when AI service cannot be reached or returns an unusable response."""


def _client(timeout: float = AICREDITS_TIMEOUT_SECONDS) -> OpenAI:
    """Initialize OpenAI client configured for AICredits endpoint."""
    if not AICREDITS_API_KEY:
        raise AIServiceError("AICREDITS_API_KEY environment variable not set")
    
    return OpenAI(
        api_key=AICREDITS_API_KEY,
        base_url=AICREDITS_BASE_URL,
        timeout=timeout,
    )


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


def generate(
    model: str,
    prompt: str,
    images: Optional[List[str]] = None,
    system: Optional[str] = None,
    format_json: bool = False,
    temperature: float = 0.0,
    max_tokens: int = 2000,
    timeout: float = AICREDITS_TIMEOUT_SECONDS,
) -> str:
    """Generate text using AICredits endpoint."""
    
    messages: List[Dict[str, Any]] = []
    
    if system:
        messages.append({"role": "system", "content": system})
    
    content: List[Dict[str, Any]] = []
    
    if images:
        for img_path in images:
            b64_img = _encode_and_resize_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_img}",
                    "detail": "auto"
                }
            })
    
    content.append({"type": "text", "text": prompt})
    messages.append({"role": "user", "content": content})
    
    last_exc: Optional[Exception] = None
    
    for attempt in range(AICREDITS_MAX_RETRIES + 1):
        try:
            client = _client(timeout=timeout)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"} if format_json else None,
            )
            result = response.choices[0].message.content
            return result if result else ""
            
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "AI service attempt %d/%d failed (model=%s): %s",
                attempt + 1,
                AICREDITS_MAX_RETRIES + 1,
                model,
                exc,
            )
    
    raise AIServiceError(f"AI service failed after retries: {last_exc}")


def chat(
    model: str,
    messages: List[Dict[str, Any]],
    format_json: bool = False,
    temperature: float = 0.0,
    max_tokens: int = 2000,
    timeout: float = AICREDITS_TIMEOUT_SECONDS,
) -> str:
    """Chat completion using AICredits endpoint."""
    
    last_exc: Optional[Exception] = None
    
    for attempt in range(AICREDITS_MAX_RETRIES + 1):
        try:
            client = _client(timeout=timeout)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"} if format_json else None,
            )
            result = response.choices[0].message.content
            return result if result else ""
            
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "AI service chat attempt %d/%d failed (model=%s): %s",
                attempt + 1,
                AICREDITS_MAX_RETRIES + 1,
                model,
                exc,
            )
    
    raise AIServiceError(f"AI service chat failed after retries: {last_exc}")


def extract_json(raw_text: str) -> Optional[Any]:
    """Extract JSON from response text, handling markdown fences."""
    if not raw_text:
        return None

    text = raw_text.strip()

    # Try markdown code fence
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try finding JSON object or array boundaries
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    logger.warning("Could not extract JSON from response: %.200s", raw_text)
    return None
