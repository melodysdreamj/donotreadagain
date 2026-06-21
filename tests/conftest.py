import math
import struct
import wave

import pytest


@pytest.fixture
def sample_pdf(tmp_path):
    """A 3-page PDF with text (+ an image if Pillow is available)."""
    from fpdf import FPDF

    img = None
    try:
        from PIL import Image

        im = Image.new("RGB", (120, 80))
        px = im.load()
        for x in range(120):
            for y in range(80):
                px[x, y] = ((x * 3) % 256, (y * 5) % 256, 90)
        img = tmp_path / "img.png"
        im.save(img)
    except Exception:
        img = None

    pdf = FPDF()
    pdf.set_font("Helvetica", size=13)
    for i in range(3):
        pdf.add_page()
        pdf.cell(0, 10, f"dnr test page {i + 1} - contract damages verbatim body",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, "The quick brown fox jumps over the lazy dog. 0123456789. " * 4)
        pdf.set_font("Helvetica", size=13)
        if img is not None:
            pdf.image(str(img), x=10, y=110, w=60)
    out = tmp_path / "doc.pdf"
    pdf.output(str(out))
    return out


@pytest.fixture
def sample_wav(tmp_path):
    out = tmp_path / "a.wav"
    sr = 8000
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for n in range(sr):
            frames += struct.pack("<h", int(30000 * math.sin(2 * math.pi * 440 * n / sr)))
        w.writeframes(frames)
    return out


@pytest.fixture
def sample_mp3(tmp_path):
    """A minimal file with fake MPEG frame bytes (no encoder needed). ID3 writes fine."""
    out = tmp_path / "a.mp3"
    out.write_bytes(b"\xff\xfb\x90\x00" + bytes(4000))
    return out


@pytest.fixture
def sample_flac(tmp_path):
    """A tiny FLAC container with valid STREAMINFO and fake frame bytes."""
    streaminfo = bytearray(34)
    streaminfo[0:2] = (4096).to_bytes(2, "big")
    streaminfo[2:4] = (4096).to_bytes(2, "big")
    val = (44100 << (3 + 5 + 36)) | (1 << (5 + 36)) | (15 << 36) | 44100
    streaminfo[10:18] = val.to_bytes(8, "big")
    out = tmp_path / "a.flac"
    out.write_bytes(b"fLaC" + bytes([0x80]) + (34).to_bytes(3, "big") +
                    bytes(streaminfo) + b"\xff\xf8" + b"\0" * 100)
    return out


def _ogg_pages(packets: list[bytes], *, serial: int) -> bytes:
    from mutagen.ogg import OggPage

    out = b""
    for i, packet in enumerate(packets):
        page = OggPage()
        page.serial = serial
        page.sequence = i
        page.position = 48000 if i == len(packets) - 1 else 0
        page.first = i == 0
        page.last = i == len(packets) - 1
        page.packets = [packet]
        out += page.write()
    return out


def _vorbis_comment(prefix: bytes) -> bytes:
    vendor = b"dnrtest"
    body = len(vendor).to_bytes(4, "little") + vendor + (0).to_bytes(4, "little")
    return prefix + body + (b"\x01" if prefix == b"\x03vorbis" else b"")


@pytest.fixture
def sample_ogg(tmp_path):
    ident = (b"\x01vorbis" + (0).to_bytes(4, "little") + bytes([2]) +
             (44100).to_bytes(4, "little") + (0).to_bytes(4, "little") * 3 +
             bytes([0x11, 1]))
    setup = b"\x05vorbis" + b"\0" * 20
    out = tmp_path / "a.ogg"
    out.write_bytes(_ogg_pages([ident, _vorbis_comment(b"\x03vorbis"), setup, b"\0audio"], serial=3))
    return out


@pytest.fixture
def sample_opus(tmp_path):
    head = (b"OpusHead" + bytes([1, 1]) + (312).to_bytes(2, "little") +
            (48000).to_bytes(4, "little") + (0).to_bytes(2, "little") + bytes([0]))
    out = tmp_path / "a.opus"
    out.write_bytes(_ogg_pages([head, _vorbis_comment(b"OpusTags"), b"\xf8\xffaudio"], serial=4))
    return out


def _mp4_box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", len(payload) + 8, kind) + payload


@pytest.fixture
def sample_m4a(tmp_path):
    """A tiny MP4/M4A container with one audio track and one media payload box."""
    full = b"\0\0\0\0"
    mdhd = _mp4_box(b"mdhd", full + struct.pack(">IIIIHH", 0, 0, 44100, 44100, 0, 0))
    hdlr = _mp4_box(b"hdlr", full + b"\0\0\0\0" + b"soun" + b"\0" * 12 + b"\0")
    mdia = _mp4_box(b"mdia", mdhd + hdlr)
    trak = _mp4_box(b"trak", mdia)
    moov = _mp4_box(b"moov", trak)
    ftyp = _mp4_box(b"ftyp", b"M4A \0\0\0\0M4A isom")
    mdat = _mp4_box(b"mdat", b"\x01\x02dnr-audio-payload" * 32)
    out = tmp_path / "a.m4a"
    out.write_bytes(ftyp + moov + mdat)
    return out


@pytest.fixture
def sample_mp4(tmp_path):
    """A tiny MP4 container; enough for MP4 freeform tags and media hash tests."""
    full = b"\0\0\0\0"
    mdhd = _mp4_box(b"mdhd", full + struct.pack(">IIIIHH", 0, 0, 30000, 30000, 0, 0))
    hdlr = _mp4_box(b"hdlr", full + b"\0\0\0\0" + b"vide" + b"\0" * 12 + b"\0")
    mdia = _mp4_box(b"mdia", mdhd + hdlr)
    trak = _mp4_box(b"trak", mdia)
    moov = _mp4_box(b"moov", trak)
    ftyp = _mp4_box(b"ftyp", b"isom\0\0\0\0isommp42")
    mdat = _mp4_box(b"mdat", b"\x00\x00dnr-video-payload" * 32)
    out = tmp_path / "v.mp4"
    out.write_bytes(ftyp + moov + mdat)
    return out


@pytest.fixture
def sample_record():
    return {
        "dnr": "0.1",
        "content_hash": "sha256:deadbeef",
        "source": {"mime": "application/pdf", "bytes": 1234},
        "transcript": {"format": "text/markdown", "lang": "ko", "text": "# hello\nbody"},
        "provenance": {"method": "text-extract", "transcriber": "pypdf"},
        "fields": {"title": "t", "tags": ["a", "b"]},
        "extras": {},
    }
