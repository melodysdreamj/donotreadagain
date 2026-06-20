"""Transcription providers (M4) — dnr does NOT own a model.

The transcript is an *input*, produced by whoever is best placed:
  - the **calling agent** (already a vision/multimodal LLM) → supplies the verbatim
    text via ``dnr record`` (primary path in an agent),
  - a **local model** (Whisper for audio, ``text-extract`` for born-digital PDFs,
    local OCR for scans),
  - optionally a hosted API.

dnr's own code only does the deterministic part (hash · record · sign · embed · index).
Providers here are the *local* ones that need no API key.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TranscriptResult:
    text: str
    method: str
    transcriber: str
    lang: str | None = None
    confidence: float | None = None
    segments: list | None = field(default=None)


def text_extract(path) -> TranscriptResult:
    """Born-digital PDF → embedded text layer, NFC-normalized. Lossless, no model."""
    from pypdf import PdfReader

    parts = []
    for page in PdfReader(str(path)).pages:
        t = page.extract_text() or ""
        parts.append(unicodedata.normalize("NFC", t))
    text = "\n\f\n".join(parts).strip()
    return TranscriptResult(text=text, method="text-extract", transcriber="pypdf")


#: name -> provider callable. Local Whisper / OCR register here later.
REGISTRY = {
    "text-extract": text_extract,
}


def get(name: str):
    if name not in REGISTRY:
        raise ValueError(
            f"unknown transcriber '{name}'. local: {sorted(REGISTRY)}; "
            f"or supply the transcript yourself via `dnr record`."
        )
    return REGISTRY[name]
