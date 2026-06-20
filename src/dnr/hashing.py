"""Hashing — the load-bearing primitives (M1).

Two hashes with different homes (vision.md §3, §6):

- ``whole_hash``   : sha256 of the entire file bytes. Index-only (chicken-and-egg
                     prevents storing a file's own whole-hash inside it). Detects
                     "anything changed".
- ``content_hash`` : sha256 of the DECODED content (not raw bytes), so it stays
                     invariant when the metadata record is embedded / the container
                     is re-serialized. Identity + the re-transcribe trigger.

Each value is prefixed with the algorithm, e.g. ``sha256:abcd…``.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

#: per-format extraction profile ids (vision.md §6) — hashes only compare within a profile
PROFILES = {
    ".pdf": "dnr-pdf-content-1",
    ".mp3": "dnr-audio-1",
    ".wav": "dnr-audio-1",
}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def whole_hash(path) -> str:
    """sha256 of the whole file bytes (index-only)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


# --------------------------------------------------------------------------- PDF
def pdf_content_hash(path) -> str:
    """Hash decompressed page content streams + image XObject bytes, in page order.

    Invariant under object renumber/reorder, Flate recompression, and metadata
    writes; sensitive to real content edits. (Validated 2026-06-20.)
    """
    import pikepdf

    h = hashlib.sha256()
    with pikepdf.open(path) as pdf:
        for page in pdf.pages:
            obj = page.obj
            contents = obj.get("/Contents")
            if contents is not None:
                streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
                for s in streams:
                    h.update(b"<CS>")
                    try:
                        h.update(bytes(s.read_bytes()))
                    except Exception:
                        h.update(bytes(s.read_raw_bytes()))
            res = obj.get("/Resources")
            xobjs = res.get("/XObject") if res is not None else None
            if xobjs is not None:
                for key in sorted(xobjs.keys(), key=str):
                    xo = xobjs[key]
                    if str(xo.get("/Subtype")) == "/Image":
                        h.update(b"<IM>")
                        try:
                            h.update(bytes(xo.read_bytes()))
                        except Exception:
                            h.update(bytes(xo.read_raw_bytes()))
    return "sha256:" + h.hexdigest()


# ------------------------------------------------------------------------- audio
def _id3v2_total_size(head: bytes) -> int:
    """Total ID3v2 header+body size given the first 10 bytes, or 0 if no ID3v2."""
    if len(head) < 10 or head[:3] != b"ID3":
        return 0
    b = head[6:10]  # 28-bit synchsafe size, excludes the 10-byte header
    size = (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]
    return 10 + size


def mp3_content_hash(path) -> str:
    """Hash the MPEG audio frames, excluding ID3v2 (front) and ID3v1 (tail)."""
    data = Path(path).read_bytes()
    start = _id3v2_total_size(data[:10])
    end = len(data)
    if end - start >= 128 and data[end - 128 : end - 125] == b"TAG":
        end -= 128
    return "sha256:" + sha256_hex(data[start:end])


def wav_content_hash(path) -> str:
    """Hash the RIFF ``data`` chunk payload (the PCM samples)."""
    b = Path(path).read_bytes()
    i = 12  # skip 'RIFF' + size + 'WAVE'
    while i + 8 <= len(b):
        cid = b[i : i + 4]
        size = int.from_bytes(b[i + 4 : i + 8], "little")
        if cid == b"data":
            return "sha256:" + sha256_hex(b[i + 8 : i + 8 + size])
        i += 8 + size + (size & 1)
    raise ValueError("no 'data' chunk found in WAV")


def text_content_hash(path) -> str:
    """Hash NFC-normalized text. Plain-text files have no metadata region to exclude."""
    import unicodedata

    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return "sha256:" + sha256_hex(unicodedata.normalize("NFC", text).encode("utf-8"))


def image_content_hash(path) -> str:
    """Hash decoded pixels + dimensions (metadata writes don't change it; re-encoding does)."""
    from PIL import Image

    with Image.open(path) as im:
        im = im.convert("RGBA")
        header = f"{im.width}x{im.height}".encode("ascii")
        pixels = im.tobytes()
    return "sha256:" + sha256_hex(header + b"|" + pixels)


def ooxml_content_hash(path) -> str:
    """Hash a sorted manifest of (member, sha256(decompressed member)), excluding the dnr part."""
    import zipfile

    with zipfile.ZipFile(path) as z:
        parts = [f"{n}:{sha256_hex(z.read(n))}" for n in sorted(z.namelist()) if not n.endswith("dnr.xml")]
    return "sha256:" + sha256_hex("\n".join(parts).encode("utf-8"))


_DISPATCH = {
    ".pdf": pdf_content_hash,
    ".mp3": mp3_content_hash,
    ".wav": wav_content_hash,
    ".txt": text_content_hash, ".md": text_content_hash, ".json": text_content_hash,
    ".csv": text_content_hash, ".tsv": text_content_hash, ".log": text_content_hash,
    ".jpg": image_content_hash, ".jpeg": image_content_hash, ".png": image_content_hash,
    ".tiff": image_content_hash, ".tif": image_content_hash, ".webp": image_content_hash,
    ".bmp": image_content_hash, ".gif": image_content_hash,
    ".docx": ooxml_content_hash, ".xlsx": ooxml_content_hash, ".pptx": ooxml_content_hash,
}


def content_hash(path) -> str:
    """Compute the canonical content_hash for a supported file."""
    ext = Path(path).suffix.lower()
    fn = _DISPATCH.get(ext)
    if fn is None:
        raise ValueError(f"no content_hash profile for '{ext}' files")
    return fn(path)
