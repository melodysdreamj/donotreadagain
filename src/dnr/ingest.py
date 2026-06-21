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
    ".pdf": "text-extract", ".docx": "docx", ".xlsx": "xlsx",
    ".mp3": "whisper", ".wav": "whisper", ".flac": "whisper",
    ".m4a": "whisper", ".ogg": "whisper", ".opus": "whisper",
}
#: already-text — no transcription and no record; read directly
TEXT_EXTS = {".txt", ".md", ".json", ".csv", ".tsv", ".log"}
#: visual/structured types that need an agent/vision transcript via `dnr record`
AGENT_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".heic", ".bmp", ".gif",
              ".mp4", ".mov", ".mkv", ".webm", ".pptx", ".html", ".rtf", ".epub"}


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
        if rec is None:
            from . import index
            rec = index.db_only_record(Path(path).parent, path)
        if rec is None or not signing.verify(rec, keyring.default_trust()):
            return None
        return rec if rec.get("content_hash") == hashing.content_hash(path) else None
    except Exception:
        return None


def _sign_and_store(path, rec: dict, *, sign: bool = True, no_embed: bool = False) -> dict:
    """Sign, then store the record **in-file** if the type has a carrier, else as a **db-only**
    record in the folder index. No sidecars. ``no_embed`` forces db-only even for a carrier type
    (leaves the original byte-identical — use when explicitly requested)."""
    if sign:
        priv, pub = keyring.default_keypair()
        rec = signing.sign(rec, priv, pub)
    if _embed.has_carrier(path) and not no_embed:
        _embed.embed(path, rec)
    else:
        from . import index
        index.put_record(Path(path).parent, path, rec)
    return rec


def ingest(path, transcriber: str | None = None, *, sign: bool = True,
           no_embed: bool = False, force: bool = False,
           model: str | None = None) -> dict | None:
    """Transcribe with a local provider (auto-selected by type), then record + sign + store.

    Already-readable text (.txt/.md/.csv/…) needs no transcription and **no record at all** —
    returns ``None`` (an agent just reads the file directly). Idempotent otherwise: skips if our
    own valid record already matches the file's content unless ``force``.
    """
    ext = Path(path).suffix.lower()
    if transcriber is None and ext in TEXT_EXTS:
        return None  # already text — no transcription, no record; read it directly
    if not force:
        existing = _already_ours(path)
        if existing is not None:
            return existing
    if transcriber is None:
        transcriber = DEFAULT_PROVIDER.get(ext)
    if transcriber is None:
        if ext in AGENT_EXTS:
            raise ValueError(
                f"{ext} needs visual/agent transcription — transcribe it yourself and run "
                f"`dnr record <file> --transcript-file <t.md> --method vision ...` (see `dnr guide`)")
        raise ValueError(f"unsupported file type '{ext}' for ingest; see `dnr types`")
    if transcriber == "whisper":
        res = transcribe.whisper_transcribe(path, model_size=model or transcribe.DEFAULT_WHISPER_MODEL)
    else:
        res = transcribe.get(transcriber)(path)
    prov = {"method": res.method, "transcriber": res.transcriber}
    if res.confidence is not None:
        prov["confidence"] = res.confidence
    rec = make_record(path, res.text, prov, lang=res.lang or transcribe.detect_lang(res.text),
                      segments=res.segments)
    return _sign_and_store(path, rec, sign=sign, no_embed=no_embed)


def backfill(folder, *, no_embed: bool = False, force: bool = False,
             model: str | None = None) -> dict:
    """Ingest a folder's locally processable files and return a machine-readable worklist.

    This deliberately does **not** do agent/vision work. Images, videos, and scanned/garbled
    results are reported for an agent to handle with `dnr record`.
    """
    import os
    import unicodedata

    from . import index

    root = Path(folder)
    stats = {
        "ingested": [],
        "already": [],
        "text": [],
        "agent_needed": [],
        "low_quality": [],
        "errors": [],
    }

    def rel(p) -> str:
        return unicodedata.normalize("NFC", os.path.relpath(p, root))

    for abspath in index._iter_files(root):
        p = Path(abspath)
        ext = p.suffix.lower()
        r = rel(p)
        if ext in TEXT_EXTS:
            stats["text"].append(r)
            continue
        if ext in AGENT_EXTS:
            stats["agent_needed"].append({"path": r, "reason": "needs agent/vision transcript"})
            continue
        if ext not in DEFAULT_PROVIDER:
            stats["agent_needed"].append({"path": r, "reason": "no local provider"})
            continue
        try:
            existed = _already_ours(p) is not None
            rec = ingest(p, no_embed=no_embed, force=force, model=model)
            if rec is None:
                stats["text"].append(r)
                continue
            item = {"path": r, "method": rec["provenance"]["method"],
                    "transcriber": rec["provenance"]["transcriber"]}
            if existed and not force:
                stats["already"].append(item)
            else:
                stats["ingested"].append(item)
            txt = (rec.get("transcript") or {}).get("text") or ""
            if transcribe.is_low_quality(txt):
                stats["low_quality"].append({"path": r, "reason": "empty/garbled/unusable transcript"})
        except Exception as exc:
            stats["errors"].append({"path": r, "error": str(exc)})

    stats["index"] = index.scan(root)
    return stats


def record_supplied(path, transcript_text: str, method: str = "vision",
                    transcriber: str = "agent", *, lang: str | None = None,
                    segments: list | None = None, tags: list | None = None,
                    fields: dict | None = None, sign: bool = True,
                    no_embed: bool = False, follows_guide: bool = True) -> dict:
    """Record a transcript produced by the agent following the verbatim guide."""
    prov = (guide.provenance_stamp(method, transcriber)
            if follows_guide else {"method": method, "transcriber": transcriber})
    fields = dict(fields or {})
    if tags:
        fields["tags"] = list(tags)
    rec = make_record(path, transcript_text, prov,
                      lang=lang or transcribe.detect_lang(transcript_text),
                      segments=segments, fields=fields or None)
    return _sign_and_store(path, rec, sign=sign, no_embed=no_embed)


def current_tags(path) -> list:
    """The tags currently on a file's record ([] if none / no record)."""
    return list((_read_record(path) or {}).get("fields", {}).get("tags") or [])


def _read_record(path) -> dict | None:
    rec = _embed.extract(path)
    if rec is None:
        from . import index
        rec = index.db_only_record(Path(path).parent, path)
    return rec


def _edit_fields(path, mutate) -> dict:
    """Load a file's record (creating a db-only one for text), apply ``mutate(fields)``, re-sign,
    re-store, and refresh the index immediately. dnr never *guesses* metadata — callers set it."""
    import unicodedata

    rec = _read_record(path)
    if rec is None:
        if Path(path).suffix.lower() in TEXT_EXTS:
            text = unicodedata.normalize("NFC", Path(path).read_text(encoding="utf-8", errors="replace"))
            rec = make_record(path, text, {"method": "none", "transcriber": "none"},
                              lang=transcribe.detect_lang(text))
        else:
            raise ValueError(f"{path} has no dnr record yet — ingest or record it first")
    fields = rec.setdefault("fields", {})
    mutate(fields)
    _sign_and_store(path, rec)
    if _embed.has_carrier(path):
        from . import index
        index.reindex_file(Path(path).parent, path)
    return fields


def set_tags(path, add: list | None = None, remove: list | None = None) -> list:
    """Add/remove tags on a file's record (explicit — dnr does not auto-tag)."""
    def _m(fields):
        tags = list(fields.get("tags") or [])
        for t in (remove or []):
            if t in tags:
                tags.remove(t)
        for t in (add or []):
            if t not in tags:
                tags.append(t)
        fields["tags"] = tags
    return _edit_fields(path, _m).get("tags") or []


def current_date(path) -> str | None:
    return (_read_record(path) or {}).get("fields", {}).get("start_date")


def set_date(path, date: str | None) -> str | None:
    """Set (or clear, with ``None``) a file's `start_date` **explicitly**. dnr never infers dates —
    they're optional; add one only when you need `--since/--until/--sort date` to apply to this file."""
    def _m(fields):
        if date:
            fields["start_date"] = date
        else:
            fields.pop("start_date", None)
    _edit_fields(path, _m)
    return date


def read_cached(path, trust: dict | None = None) -> str | None:
    """Return the cached transcript iff a trusted record matches; else None.

    Skip-reparse gate: present record + valid signature from a trusted key +
    content_hash matches the file. Anything else -> None (read normally).
    """
    try:
        rec = _embed.extract(path)
        if rec is None:  # no in-file carrier? try a db-only record in the folder index
            from . import index
            rec = index.db_only_record(Path(path).parent, path)
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
