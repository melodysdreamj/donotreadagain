"""Transcription providers (M4) — dnr does NOT own a model.

The transcript is an *input*, produced by whoever is best placed:
  - the **calling agent** (already a vision/multimodal LLM) -> supplies the verbatim
    text via ``dnr record`` (primary path for visual docs / images / scans),
  - a **local model** (Whisper for audio, ``text-extract`` for born-digital PDFs,
    local OCR for scans),
  - optionally a hosted API.

Providers here are the *local* ones. The agent path lives in ``ingest.record_supplied``.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


@dataclass
class TranscriptResult:
    text: str
    method: str
    transcriber: str
    lang: str | None = None
    confidence: float | None = None
    segments: list | None = field(default=None)


def text_extract(path) -> TranscriptResult:
    """Born-digital PDF -> embedded text layer, NFC-normalized. Lossless, no model."""
    from pypdf import PdfReader

    parts = []
    for page in PdfReader(str(path)).pages:
        t = page.extract_text() or ""
        parts.append(unicodedata.normalize("NFC", t))
    text = "\n\f\n".join(parts).strip()
    return TranscriptResult(text=text, method="text-extract", transcriber="pypdf")


def whisper_transcribe(path, model_size: str = "base") -> TranscriptResult:
    """Local ASR for audio via faster-whisper. Verbatim by construction; timestamps."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # optional heavy dep + model download
        raise RuntimeError(
            "the 'whisper' provider needs faster-whisper (pip install faster-whisper), "
            "or supply the transcript via `dnr record`."
        ) from exc

    model = WhisperModel(model_size, compute_type="int8")
    segments, info = model.transcribe(str(path))
    segs, parts = [], []
    for s in segments:
        t = s.text.strip()
        segs.append({"t": round(s.start, 3), "text": t})
        parts.append(t)
    return TranscriptResult(
        text="\n".join(parts),
        method="asr",
        transcriber=f"faster-whisper-{model_size}",
        lang=getattr(info, "language", None),
        segments=segs,
    )


#: name -> local provider callable. Local OCR / vision register here later.
REGISTRY = {
    "text-extract": text_extract,
    "whisper": whisper_transcribe,
}


def get(name: str):
    if name not in REGISTRY:
        raise ValueError(
            f"unknown transcriber '{name}'. local: {sorted(REGISTRY)}; "
            f"or supply the transcript yourself via `dnr record`."
        )
    return REGISTRY[name]
