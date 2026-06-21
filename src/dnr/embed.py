"""Embed / extract carriers (M2).

Write the record into a file's native metadata slot, read it back.
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
import warnings
from pathlib import Path

# pikepdf emits this UserWarning when reading XMP whose dc:* fields repeat (common in real
# PDFs); harmless for our read/round-trip, but noisy on every extract/index. Silence just it.
warnings.filterwarnings("ignore", message="Merging elements of")

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


# ------------------------------------------------------------ legacy sidecar IO
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

    try:
        with pikepdf.open(path) as pdf:
            with pdf.open_metadata() as meta:
                v = meta.get("dc:description")
    except Exception:
        return None  # unreadable / corrupt PDF -> no record (caller falls back)
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
    except Exception:  # no header / corrupt -> no record
        return None
    for fr in tags.getall("TXXX"):
        if fr.desc == "dnr":
            try:
                return json.loads(fr.text[0])
            except (ValueError, TypeError, IndexError):
                return None
    return None


# ------------------------------------------------------------------------- mp4
_MP4_DNR_KEY = "----:com.donotreadagain:record"


def embed_mp4(path, record: dict) -> None:
    from mutagen.mp4 import MP4, MP4FreeForm

    js = _dump(record).encode("utf-8")
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        tags = MP4(tmp)
        if tags.tags is None:
            tags.add_tags()
        tags.tags[_MP4_DNR_KEY] = [MP4FreeForm(js, dataformat=1)]
        tags.save()
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def extract_mp4(path):
    from mutagen.mp4 import MP4

    try:
        tags = MP4(path).tags
    except Exception:
        return None
    if not tags:
        return None
    vals = tags.get(_MP4_DNR_KEY)
    if not vals:
        return None
    try:
        return json.loads(bytes(vals[0]).decode("utf-8"))
    except (ValueError, TypeError, IndexError, UnicodeDecodeError):
        return None


# ----------------------------------------------------------------- vorbis tags
_VORBIS_DNR_KEY = "DNR_RECORD"


def embed_flac(path, record: dict) -> None:
    from mutagen.flac import FLAC

    js = _dump(record)
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        tags = FLAC(tmp)
        if tags.tags is None:
            tags.add_tags()
        tags[_VORBIS_DNR_KEY] = [js]
        tags.save()
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def extract_flac(path):
    from mutagen.flac import FLAC

    try:
        tags = FLAC(path)
    except Exception:
        return None
    vals = tags.get(_VORBIS_DNR_KEY)
    if not vals:
        return None
    try:
        return json.loads(vals[0])
    except (ValueError, TypeError, IndexError):
        return None


def _ogg_class(path):
    if Path(path).suffix.lower() == ".opus":
        from mutagen.oggopus import OggOpus
        return OggOpus
    from mutagen.oggvorbis import OggVorbis
    return OggVorbis


def embed_ogg(path, record: dict) -> None:
    js = _dump(record)
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        tags = _ogg_class(path)(tmp)
        tags[_VORBIS_DNR_KEY] = [js]
        tags.save()
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def extract_ogg(path):
    try:
        tags = _ogg_class(path)(path)
    except Exception:
        return None
    vals = tags.get(_VORBIS_DNR_KEY)
    if not vals:
        return None
    try:
        return json.loads(vals[0])
    except (ValueError, TypeError, IndexError):
        return None


# ------------------------------------------------------------------------ PNG
# Lossless: decode→encode preserves pixels, so content_hash (decoded pixels) is invariant.
def embed_png(path, record: dict) -> None:
    from PIL import Image, PngImagePlugin

    js = _dump(record)
    with Image.open(path) as im:
        im.load()
        info = PngImagePlugin.PngInfo()
        for k, v in (getattr(im, "text", {}) or {}).items():
            if k != "dnr":
                info.add_itxt(k, v)
        info.add_itxt("dnr", js)  # iTXt = UTF-8 (record JSON may be non-ASCII)
        d = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
        os.close(fd)
        try:
            im.save(tmp, format="PNG", pnginfo=info, optimize=False)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def extract_png(path):
    from PIL import Image

    try:
        with Image.open(path) as im:
            v = (getattr(im, "text", {}) or {}).get("dnr")
    except Exception:
        return None
    if not v:
        return None
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return None


def strip_png(path) -> bool:
    from PIL import Image, PngImagePlugin

    if extract_png(path) is None:
        return False
    with Image.open(path) as im:
        im.load()
        info = PngImagePlugin.PngInfo()
        for k, v in (getattr(im, "text", {}) or {}).items():
            if k != "dnr":
                info.add_itxt(k, v)
        d = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
        os.close(fd)
        try:
            im.save(tmp, format="PNG", pnginfo=info, optimize=False)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    return True


# ----------------------------------------------------------------------- JPEG
# Byte-level: insert our record as APP11 segment(s) right after SOI without touching the
# compressed scan, so decoded pixels (and content_hash) are unchanged. Chunked for >64KB.
_JPG_MAGIC = b"dnr\x00"
_JPG_MARKER = 0xEB  # APP11
_JPG_MAXC = 65533 - len(_JPG_MAGIC) - 2  # segment payload cap minus magic + (total,idx) bytes


def _jpeg_leading(data: bytes):
    """(leading APPn/COM segments as [(marker, payload)], offset where the body starts)."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    pos, segs = 2, []
    while pos + 4 <= len(data) and data[pos] == 0xFF and (0xE0 <= data[pos + 1] <= 0xEF or data[pos + 1] == 0xFE):
        marker = data[pos + 1]
        ln = int.from_bytes(data[pos + 2:pos + 4], "big")
        segs.append((marker, data[pos + 4:pos + 2 + ln]))
        pos += 2 + ln
    return segs, pos


def _jpeg_write(data: bytes, record: dict | None) -> bytes:
    segs, body = _jpeg_leading(data)
    keep = [(m, p) for (m, p) in segs if not (m == _JPG_MARKER and p.startswith(_JPG_MAGIC))]
    new = []
    if record is not None:
        js = _dump(record).encode("utf-8")
        chunks = [js[i:i + _JPG_MAXC] for i in range(0, len(js), _JPG_MAXC)] or [b""]
        for i, c in enumerate(chunks):
            new.append((_JPG_MARKER, _JPG_MAGIC + bytes([len(chunks), i]) + c))
    out = b"\xff\xd8"
    for m, p in keep + new:
        out += bytes([0xFF, m]) + (len(p) + 2).to_bytes(2, "big") + p
    return out + data[body:]


def embed_jpeg(path, record: dict) -> None:
    _atomic_replace(path, _jpeg_write(Path(path).read_bytes(), record))


def extract_jpeg(path):
    try:
        data = Path(path).read_bytes()
        segs, _ = _jpeg_leading(data)
    except Exception:
        return None
    parts, total = {}, None
    for m, p in segs:
        if m == _JPG_MARKER and p.startswith(_JPG_MAGIC):
            total, idx = p[4], p[5]
            parts[idx] = p[6:]
    if total is None:
        return None
    try:
        return json.loads(b"".join(parts[i] for i in range(total)))
    except (ValueError, TypeError, KeyError):
        return None


def strip_jpeg(path) -> bool:
    if extract_jpeg(path) is None:
        return False
    _atomic_replace(path, _jpeg_write(Path(path).read_bytes(), None))
    return True


# ---------------------------------------------------------------------- dispatch
_EMBED = {".pdf": embed_pdf, ".mp3": embed_mp3, ".png": embed_png,
          ".jpg": embed_jpeg, ".jpeg": embed_jpeg,
          ".m4a": embed_mp4, ".mp4": embed_mp4, ".mov": embed_mp4,
          ".flac": embed_flac, ".ogg": embed_ogg, ".opus": embed_ogg}
_EXTRACT = {".pdf": extract_pdf, ".mp3": extract_mp3, ".png": extract_png,
            ".jpg": extract_jpeg, ".jpeg": extract_jpeg,
            ".m4a": extract_mp4, ".mp4": extract_mp4, ".mov": extract_mp4,
            ".flac": extract_flac, ".ogg": extract_ogg, ".opus": extract_ogg}


def has_carrier(path) -> bool:
    """True if this file type can hold the record **in-file** (else use a db-only record)."""
    return Path(path).suffix.lower() in _EMBED


def embed(path, record: dict) -> None:
    """Embed the record into the file's native in-file slot. No sidecars.

    For a type with no in-file carrier, raise — the caller stores a **db-only** record in the
    folder index instead (`dnr.index.put_record`); we never write a `.dnr.json` sidecar.
    """
    ext = Path(path).suffix.lower()
    fn = _EMBED.get(ext)
    if fn is None:
        raise ValueError(f"no in-file carrier for '{ext}' — store a db-only record in the index instead")
    fn(path, record)


def extract(path):
    """Read the record from the file's native in-file slot (None if absent/unsupported)."""
    fn = _EXTRACT.get(Path(path).suffix.lower())
    return fn(path) if fn is not None else None


# -------------------------------------------------------------------------- strip
def strip_pdf(path) -> bool:
    import pikepdf

    if extract_pdf(path) is None:
        return False
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                try:
                    del meta["dc:description"]
                except Exception:
                    pass
            pdf.save(tmp, deterministic_id=True)
        os.replace(tmp, path)
        return True
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def strip_mp3(path) -> bool:
    from mutagen.id3 import ID3

    try:
        tags = ID3(path)
    except Exception:
        return False
    if not tags.getall("TXXX:dnr"):
        return False
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        t = ID3(tmp)
        t.delall("TXXX:dnr")
        t.save(tmp, padding=lambda _i: 0)
        os.replace(tmp, path)
        return True
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def strip_mp4(path) -> bool:
    from mutagen.mp4 import MP4

    try:
        tags = MP4(path)
    except Exception:
        return False
    if not tags.tags or _MP4_DNR_KEY not in tags.tags:
        return False
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        t = MP4(tmp)
        if t.tags and _MP4_DNR_KEY in t.tags:
            del t.tags[_MP4_DNR_KEY]
            t.save()
        os.replace(tmp, path)
        return True
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def strip_flac(path) -> bool:
    from mutagen.flac import FLAC

    try:
        tags = FLAC(path)
    except Exception:
        return False
    if not tags.get(_VORBIS_DNR_KEY):
        return False
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        t = FLAC(tmp)
        if t.get(_VORBIS_DNR_KEY):
            del t[_VORBIS_DNR_KEY]
            t.save()
        os.replace(tmp, path)
        return True
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def strip_ogg(path) -> bool:
    try:
        tags = _ogg_class(path)(path)
    except Exception:
        return False
    if not tags.get(_VORBIS_DNR_KEY):
        return False
    data = Path(path).read_bytes()
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".dnrtmp")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        t = _ogg_class(path)(tmp)
        if t.get(_VORBIS_DNR_KEY):
            del t[_VORBIS_DNR_KEY]
            t.save()
        os.replace(tmp, path)
        return True
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


_STRIP = {".pdf": strip_pdf, ".mp3": strip_mp3, ".png": strip_png,
          ".jpg": strip_jpeg, ".jpeg": strip_jpeg,
          ".m4a": strip_mp4, ".mp4": strip_mp4, ".mov": strip_mp4,
          ".flac": strip_flac, ".ogg": strip_ogg, ".opus": strip_ogg}


def strip(path) -> bool:
    """Remove the dnr record (in-file slot + any legacy sidecar). True if anything was removed.

    Use before sharing a file to avoid leaking the embedded transcript / summary / entities.
    Content is unchanged (content_hash is invariant).
    """
    ext = Path(path).suffix.lower()
    removed = False
    fn = _STRIP.get(ext)
    if fn is not None:
        removed = fn(path) or removed
    sp = sidecar_path(path)
    if os.path.exists(sp):
        os.remove(sp)
        removed = True
    return removed
