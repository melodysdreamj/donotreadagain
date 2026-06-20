"""Ingest pipeline + consumer read (M4).

`ingest`         : content_hash -> transcribe (local provider, auto by type) -> record -> sign -> embed.
`record_supplied`: the **agent** path — the agent transcribes (following the guide) and supplies the text.
`read_cached`    : consumer side — return the cached transcript iff a *trusted* record matches the file.

No timestamps are written, so re-ingesting identical content with the same model yields a
byte-identical record (idempotent — vision.md §16 gate 4).
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from . import embed as _embed
from . import guide, hashing, keyring, signing, transcribe
from . import record as _record

#: default local transcriber by extension — audio -> Whisper, born-digital PDF -> text-extract
DEFAULT_PROVIDER = {
    ".pdf": "text-extract", ".docx": "docx",
    ".mp3": "whisper", ".wav": "whisper", ".flac": "whisper",
    ".m4a": "whisper", ".ogg": "whisper", ".opus": "whisper",
}
#: already-text — no transcription (method=none), stored as a sidecar
TEXT_EXTS = {".txt", ".md", ".json", ".csv", ".tsv", ".log"}
#: visual/structured types that need an agent/vision transcript via `dnr record`
AGENT_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".heic", ".bmp", ".gif",
              ".mp4", ".mov", ".mkv", ".webm", ".pptx", ".xlsx", ".html", ".rtf", ".epub"}


def _mime(path) -> str:
    m, _ = mimetypes.guess_type(str(path))
    return m or "application/octet-stream"


def make_record(path, transcript_text: str, provenance: dict, *,
                lang: str | None = None, segments: list | None = None,
                fields: dict | None = None) -> dict:
    transcript: dict = {"format": "text/markdown", "text": transcript_text}
    if lang:
        transcript["lang"] = lang
    if segments:
        transcript["segments"] = segments
    return _record.new_record(
        content_hash=hashing.content_hash(path),
        source={"mime": _mime(path), "bytes": Path(path).stat().st_size},
        transcript=transcript,
        provenance=provenance,
        fields=fields or {},
    )


def _already_ours(path) -> dict | None:
    try:
        rec = _embed.extract(path)
        if rec is None or not signing.verify(rec, keyring.default_trust()):
            return None
        return rec if rec.get("content_hash") == hashing.content_hash(path) else None
    except Exception:
        return None


def _sign_and_embed(path, rec: dict, *, sign: bool, sidecar: bool) -> dict:
    if sign:
        priv, pub = keyring.default_keypair()
        rec = signing.sign(rec, priv, pub)
    _embed.embed(path, rec, sidecar=sidecar)
    return rec


def ingest(path, transcriber: str | None = None, *, sign: bool = True,
           sidecar: bool = False, force: bool = False) -> dict:
    """Transcribe with a local provider (auto-selected by type), then record + sign + embed.

    Idempotent: skips if our own valid record already matches the file's content (the
    producer gate that prevents re-ingest churn) unless ``force``.
    """
    if not force:
        existing = _already_ours(path)
        if existing is not None:
            return existing
    ext = Path(path).suffix.lower()
    if transcriber is None and ext in TEXT_EXTS:
        return _ingest_text(path, sign=sign)
    if transcriber is None:
        transcriber = DEFAULT_PROVIDER.get(ext)
    if transcriber is None:
        if ext in AGENT_EXTS:
            raise ValueError(
                f"{ext} needs visual/agent transcription — transcribe it yourself and run "
                f"`dnr record <file> --transcript-file <t.md> --method vision ...` (see `dnr guide`)")
        raise ValueError(f"unsupported file type '{ext}' for ingest; see `dnr types`")
    res = transcribe.get(transcriber)(path)
    prov = {"method": res.method, "transcriber": res.transcriber}
    if res.confidence is not None:
        prov["confidence"] = res.confidence
    rec = make_record(path, res.text, prov, lang=res.lang, segments=res.segments)
    return _sign_and_embed(path, rec, sign=sign, sidecar=sidecar)


def _ingest_text(path, *, sign: bool = True) -> dict:
    """Text files need no transcription (method=none); store a sidecar record."""
    import unicodedata

    text = unicodedata.normalize("NFC", Path(path).read_text(encoding="utf-8", errors="replace"))
    rec = make_record(path, text, {"method": "none", "transcriber": "none"})
    return _sign_and_embed(path, rec, sign=sign, sidecar=True)


def record_supplied(path, transcript_text: str, method: str = "vision",
                    transcriber: str = "agent", *, lang: str | None = None,
                    segments: list | None = None, sign: bool = True,
                    sidecar: bool = False, follows_guide: bool = True) -> dict:
    """Record a transcript produced by the agent following the verbatim guide."""
    prov = (guide.provenance_stamp(method, transcriber)
            if follows_guide else {"method": method, "transcriber": transcriber})
    rec = make_record(path, transcript_text, prov, lang=lang, segments=segments)
    return _sign_and_embed(path, rec, sign=sign, sidecar=sidecar)


def read_cached(path, trust: dict | None = None) -> str | None:
    """Return the cached transcript iff a trusted record matches; else None.

    Skip-reparse gate: present record + valid signature from a trusted key +
    content_hash matches the file. Anything else -> None (read normally).
    """
    try:
        rec = _embed.extract(path)
        if rec is None:
            return None
        trust = keyring.default_trust() if trust is None else trust
        if not signing.verify(rec, trust):
            return None
        if rec.get("content_hash") != hashing.content_hash(path):
            return None
        return (rec.get("transcript") or {}).get("text")
    except Exception:
        return None  # missing / corrupt file -> cache miss -> caller reads normally
