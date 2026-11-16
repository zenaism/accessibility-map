"""Describe a picture that OCR cannot read well (a map, a floor plan, a sign, a poster) with a small local vision model.

Free and offline (Ollama, `qwen2.5vl:3b`). Slow on a laptop (tens of seconds per image), so it is used only on images whose
OCR text is short, within a budget, and every answer is cached by the image's hash. The description is a lead for a person
or a later extractor, never a fact on its own: it is stored with method "vision" and a modest confidence.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json

import requests

from ..core import ROOT
from .llm import OLLAMA

MODEL = "llava-phi3"
PROMPT_VERSION = "v1"
CACHE = ROOT / "data" / "cache" / "vision.jsonl"
MAX_SIDE = 1024
SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["map", "floor_plan", "sign", "poster", "photo", "diagram", "other"],
        },
        "summary": {"type": "string"},
        "accessibility_items": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["kind", "summary", "accessibility_items"],
}
PROMPT = (
    "Describe this image for someone planning a visit with a wheelchair or low vision. "
    "kind: what the image is. summary: one or two sentences about what it shows. "
    "accessibility_items: short phrases for anything about accessibility that is visible: wheelchair symbols, ramps, "
    "elevators, accessible entrances, accessible parking, restrooms, steps, steep or rough paths, trail surfaces, "
    "distances. Use only what you can see. If there is none, return an empty list."
)
_cache: dict[str, dict] | None = None


def available() -> bool:
    try:
        tags = requests.get(f"{OLLAMA}/api/tags", timeout=3).json()
        return any(m["name"] == MODEL for m in tags.get("models", []))
    except (requests.RequestException, ValueError):
        return False


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = {}
        if CACHE.exists():
            for line in CACHE.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    _cache[r["key"]] = r["answer"]
    return _cache


def _prepare(data: bytes) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _ask(image_jpeg: bytes) -> dict:
    r = requests.post(
        f"{OLLAMA}/api/chat",
        json={
            "model": MODEL,
            "stream": False,
            "format": SCHEMA,
            "keep_alive": "10m",
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 300},
            "messages": [
                {"role": "user", "content": PROMPT, "images": [base64.b64encode(image_jpeg).decode()]}
            ],
        },
        timeout=600,
    )
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


def describe(data: bytes) -> dict | None:
    """{kind, summary, accessibility_items} for an image, or None when the model is unavailable or the image unreadable."""
    key = hashlib.sha256(f"{MODEL}|{PROMPT_VERSION}|".encode() + data).hexdigest()
    cache = _load()
    if key in cache:
        return cache[key]
    try:
        ans = _ask(_prepare(data))
    except (requests.RequestException, ValueError, KeyError, OSError):
        return None
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with CACHE.open("a") as f:
        f.write(json.dumps({"key": key, "answer": ans}) + "\n")
    cache[key] = ans
    return ans
