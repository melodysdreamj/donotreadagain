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


def detect_lang(text: str | None) -> str | None:
    """Cheap, deterministic, dependency-free script heuristic (ko / zh / ja / en)."""
    if not text:
        return None
    han = cjk = kana = latin = 0
    for c in text:
        o = ord(c)
        if 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF:
            han += 1
        elif 0x3040 <= o <= 0x30FF:
            kana += 1
        elif 0x4E00 <= o <= 0x9FFF:
            cjk += 1
        elif c.isascii() and c.isalpha():
            latin += 1
    if han and han >= cjk:
        return "ko"
    if kana:
        return "ja"
    if cjk:
        return "zh"
    if latin:
        return "en"
    return None


def is_low_quality(text: str | None) -> bool:
    """Cheap heuristic: is this transcript empty or **garbled** (e.g. EUC-KR/CP949 decoded as
    Latin-1 → mojibake)? We don't try to *fix* it — that's the vision/`dnr record` path's job;
    we just flag it so it isn't silently trusted."""
    if not text or len(text.strip()) < 3:
        return True
    s = text.strip()
    ok_ascii = " \t\n\r.,;:!?()[]{}'\"/\\-–—…%₩$+*=&@#·"
    readable = 0
    for c in s:
        o = ord(c)
        if 0xAC00 <= o <= 0xD7A3 or 0x4E00 <= o <= 0x9FFF or 0x3040 <= o <= 0x30FF:  # Hangul / CJK / kana
            readable += 1
        elif c.isascii() and (c.isalnum() or c in ok_ascii):
            readable += 1
    return readable / len(s) < 0.55  # mostly unreadable bytes -> mojibake / garbage


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


def docx_extract(path) -> TranscriptResult:
    """Born-digital Word document -> paragraph text via python-docx. Local, no model."""
    import docx

    document = docx.Document(str(path))
    text = "\n".join(p.text for p in document.paragraphs)
    return TranscriptResult(text=unicodedata.normalize("NFC", text), method="text-extract", transcriber="python-docx")


#: name -> local provider callable. Local OCR / vision register here later.
REGISTRY = {
    "text-extract": text_extract,
    "whisper": whisper_transcribe,
    "docx": docx_extract,
}


def get(name: str):
    if name not in REGISTRY:
        raise ValueError(
            f"unknown transcriber '{name}'. local: {sorted(REGISTRY)}; "
            f"or supply the transcript yourself via `dnr record`."
        )
    return REGISTRY[name]
