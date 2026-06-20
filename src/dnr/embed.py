"""Embed / extract carriers (M2).

Write the record into a file's native metadata slot (or a sidecar), read it back.
All writes are **atomic** (temp + fsync + rename) and **deterministic** so re-embed
keeps whole_hash stable (conformance gates 2-4, vision.md §13, §16).

NOTE (v0.1 interim): PDF stores the record in XMP ``dc:description`` — the proven,
deterministic carrier from the make-or-break experiment. The spec target is a custom
``dnr:record`` namespace; promoting it is M2 follow-up work. content_hash invariance,
round-trip, and determinism already hold with this carrier.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path

DNR_NS = "https://ns.donotreadagain.org/1.0/"


def _dump(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _atomic_replace(path, data: bytes) -> None:
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------- sidecar
def sidecar_path(path) -> str:
    return str(path) + ".dnr.json"


def embed_sidecar(path, record: dict) -> None:
    _atomic_replace(sidecar_path(path), json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"))


def extract_sidecar(path):
    p = sidecar_path(path)
    return json.loads(Path(p).read_bytes()) if os.path.exists(p) else None


# ------------------------------------------------------------------------- PDF
def embed_pdf(path, record: dict) -> None:
    import pikepdf

    js = _dump(record)
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                meta["dc:description"] = js
                for k in ("xmp:MetadataDate", "xmp:ModifyDate", "xmp:CreateDate"):
                    try:
                        del meta[k]
                    except Exception:
                        pass
            for k in ("/ModDate", "/CreationDate"):
                try:
                    del pdf.docinfo[k]
                except Exception:
                    pass
            pdf.save(tmp, deterministic_id=True)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def extract_pdf(path):
    import pikepdf

    with pikepdf.open(path) as pdf:
        with pdf.open_metadata() as meta:
            v = meta.get("dc:description")
    if not v:
        return None
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------------------- mp3
def embed_mp3(path, record: dict) -> None:
    from mutagen.id3 import ID3, TXXX, ID3NoHeaderError

    js = _dump(record)
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        try:
            tags = ID3(tmp)
        except ID3NoHeaderError:
            tags = ID3()
        tags.delall("TXXX:dnr")
        tags.add(TXXX(encoding=3, desc="dnr", text=[js]))
        tags.save(tmp, padding=lambda _info: 0)  # deterministic: no padding drift
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def extract_mp3(path):
    from mutagen.id3 import ID3, ID3NoHeaderError

    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        return None
    for fr in tags.getall("TXXX"):
        if fr.desc == "dnr":
            try:
                return json.loads(fr.text[0])
            except (ValueError, TypeError, IndexError):
                return None
    return None


# ---------------------------------------------------------------------- dispatch
_EMBED = {".pdf": embed_pdf, ".mp3": embed_mp3}
_EXTRACT = {".pdf": extract_pdf, ".mp3": extract_mp3}


def embed(path, record: dict, *, sidecar: bool = False) -> None:
    """Embed into the native slot, or write a sidecar when no in-file slot fits."""
    ext = Path(path).suffix.lower()
    fn = None if sidecar else _EMBED.get(ext)
    if fn is None:
        embed_sidecar(path, record)
    else:
        fn(path, record)


def extract(path):
    """Read the record from the native slot, falling back to a sidecar."""
    ext = Path(path).suffix.lower()
    fn = _EXTRACT.get(ext)
    rec = fn(path) if fn is not None else None
    return rec if rec is not None else extract_sidecar(path)
