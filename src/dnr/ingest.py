"""Ingest pipeline + consumer read (M4 / M10 consumer path).

`ingest`         : content_hash → transcribe (local provider) → record → sign → embed.
`record_supplied`: same, but the transcript is supplied by the agent (no local model).
`read_cached`    : the consumer side — return the cached transcript iff a *trusted*
                   record matches the file, else None (caller reads normally).

No timestamps are written, so re-ingesting identical content with the same model
yields a byte-identical record (idempotent — vision.md §16 gate 4).
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from . import embed as _embed
from . import hashing, keyring, signing, transcribe
from . import record as _record


def _mime(path) -> str:
    m, _ = mimetypes.guess_type(str(path))
    return m or "application/octet-stream"


def make_record(path, transcript_text: str, method: str, transcriber: str,
                *, lang: str | None = None, confidence: float | None = None,
                segments: list | None = None, fields: dict | None = None) -> dict:
    transcript: dict = {"format": "text/markdown", "text": transcript_text}
    if lang:
        transcript["lang"] = lang
    if segments:
        transcript["segments"] = segments
    prov: dict = {"method": method, "transcriber": transcriber}
    if confidence is not None:
        prov["confidence"] = confidence
    return _record.new_record(
        content_hash=hashing.content_hash(path),
        source={"mime": _mime(path), "bytes": Path(path).stat().st_size},
        transcript=transcript,
        provenance=prov,
        fields=fields or {},
    )


def _sign_and_embed(path, rec: dict, *, sign: bool, sidecar: bool) -> dict:
    if sign:
        priv, pub = keyring.default_keypair()
        rec = signing.sign(rec, priv, pub)
    _embed.embed(path, rec, sidecar=sidecar)
    return rec


def ingest(path, transcriber: str = "text-extract", *, sign: bool = True,
           sidecar: bool = False, force: bool = False) -> dict:
    """Transcribe with a local provider, then record + sign + embed.

    Idempotent: if our own valid record already matches the file's content, skip
    (no re-transcription, no re-embed) unless ``force``. This is the producer gate
    that prevents re-ingest churn (vision.md §7, §16 gate 4).
    """
    if not force:
        existing = _embed.extract(path)
        if existing is not None and signing.verify(existing, keyring.default_trust()):
            try:
                if existing.get("content_hash") == hashing.content_hash(path):
                    return existing
            except ValueError:
                pass
    res = transcribe.get(transcriber)(path)
    rec = make_record(path, res.text, res.method, res.transcriber,
                      lang=res.lang, confidence=res.confidence, segments=res.segments)
    return _sign_and_embed(path, rec, sign=sign, sidecar=sidecar)


def record_supplied(path, transcript_text: str, method: str, transcriber: str,
                    *, lang: str | None = None, sign: bool = True,
                    sidecar: bool = False) -> dict:
    """Record a transcript produced by the agent (no local model)."""
    rec = make_record(path, transcript_text, method, transcriber, lang=lang)
    return _sign_and_embed(path, rec, sign=sign, sidecar=sidecar)


def read_cached(path, trust: dict | None = None) -> str | None:
    """Return the cached transcript iff a trusted record matches; else None.

    This is the skip-reparse gate: present record + valid signature from a trusted
    key + content_hash matches the file. Anything else → None (read normally).
    """
    rec = _embed.extract(path)
    if rec is None:
        return None
    trust = keyring.default_trust() if trust is None else trust
    if not signing.verify(rec, trust):
        return None
    if rec.get("content_hash") != hashing.content_hash(path):
        return None
    return (rec.get("transcript") or {}).get("text")
