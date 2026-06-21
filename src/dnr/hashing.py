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
    ".m4a": "dnr-mp4-media-1",
    ".mp4": "dnr-mp4-media-1",
    ".mov": "dnr-mp4-media-1",
    ".flac": "dnr-flac-audio-1",
    ".ogg": "dnr-ogg-packets-1",
    ".opus": "dnr-ogg-packets-1",
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


def mp4_content_hash(path) -> str:
    """Hash MP4/M4A/MOV media payloads, excluding container metadata atoms.

    Freeform tags live under ``moov.udta.meta`` and may change when dnr embeds a record.
    The encoded audio/video payload is stored in one or more top-level ``mdat`` boxes, so
    hashing those payloads gives us the same invariance property as MP3/WAV carriers.
    """
    data = Path(path).read_bytes()
    h = hashlib.sha256()
    found = False
    i = 0
    n = len(data)
    while i + 8 <= n:
        size = int.from_bytes(data[i:i + 4], "big")
        typ = data[i + 4:i + 8]
        header = 8
        if size == 1:
            if i + 16 > n:
                break
            size = int.from_bytes(data[i + 8:i + 16], "big")
            header = 16
        elif size == 0:
            size = n - i
        if size < header or i + size > n:
            break
        if typ == b"mdat":
            found = True
            h.update(b"<MDAT>")
            h.update(data[i + header:i + size])
        i += size
    if not found:
        raise ValueError("no 'mdat' box found in MP4/M4A/MOV")
    return "sha256:" + h.hexdigest()


def flac_content_hash(path) -> str:
    """Hash FLAC audio frames, excluding FLAC metadata blocks."""
    data = Path(path).read_bytes()
    if not data.startswith(b"fLaC"):
        raise ValueError("not a FLAC file")
    i = 4
    while i + 4 <= len(data):
        block_header = data[i]
        length = int.from_bytes(data[i + 1:i + 4], "big")
        i += 4 + length
        if block_header & 0x80:
            break
    if i > len(data):
        raise ValueError("truncated FLAC metadata")
    return "sha256:" + sha256_hex(data[i:])


def _ogg_packets(path):
    """Yield complete logical packets from an Ogg stream."""
    from mutagen.ogg import OggPage

    pending = b""
    with open(path, "rb") as f:
        while True:
            try:
                page = OggPage(f)
            except EOFError:
                break
            packets = list(page.packets)
            if page.continued and packets:
                packets[0] = pending + packets[0]
                pending = b""
            if not page.complete and packets:
                pending = packets.pop()
            for packet in packets:
                yield packet


def ogg_content_hash(path) -> str:
    """Hash Ogg Vorbis/Opus stream packets while excluding comment/tag packets."""
    h = hashlib.sha256()
    first = None
    hashed = False
    for i, packet in enumerate(_ogg_packets(path)):
        if i == 0:
            first = packet
        is_vorbis_comment = (
            i == 1 and first and first.startswith(b"\x01vorbis") and packet.startswith(b"\x03vorbis")
        )
        is_opus_tags = (
            i == 1 and first and first.startswith(b"OpusHead") and packet.startswith(b"OpusTags")
        )
        if is_vorbis_comment or is_opus_tags:
            continue
        hashed = True
        h.update(b"<PKT>")
        h.update(packet)
    if not hashed:
        raise ValueError("no Ogg packets found")
    return "sha256:" + h.hexdigest()


def text_content_hash(path) -> str:
    """Hash NFC-normalized text. Plain-text files have no metadata region to exclude."""
    import unicodedata

    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return "sha256:" + sha256_hex(unicodedata.normalize("NFC", text).encode("utf-8"))


def image_content_hash(path) -> str:
    """Hash decoded pixels + dimensions (metadata writes don't change it; re-encoding does)."""
    from PIL import Image

    if Path(path).suffix.lower() in {".heic", ".heif"}:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except Exception as exc:
            raise ValueError("HEIC/HEIF content_hash requires the optional pillow-heif package") from exc

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
    ".m4a": mp4_content_hash, ".mp4": mp4_content_hash, ".mov": mp4_content_hash,
    ".flac": flac_content_hash, ".ogg": ogg_content_hash, ".opus": ogg_content_hash,
    ".txt": text_content_hash, ".md": text_content_hash, ".json": text_content_hash,
    ".csv": text_content_hash, ".tsv": text_content_hash, ".log": text_content_hash,
    ".jpg": image_content_hash, ".jpeg": image_content_hash, ".png": image_content_hash,
    ".tiff": image_content_hash, ".tif": image_content_hash, ".webp": image_content_hash,
    ".bmp": image_content_hash, ".gif": image_content_hash, ".heic": image_content_hash, ".heif": image_content_hash,
    ".docx": ooxml_content_hash, ".xlsx": ooxml_content_hash, ".pptx": ooxml_content_hash,
}


def content_hash(path) -> str:
    """Compute the canonical content_hash for a supported file."""
    ext = Path(path).suffix.lower()
    fn = _DISPATCH.get(ext)
    if fn is None:
        raise ValueError(f"no content_hash profile for '{ext}' files")
    return fn(path)
