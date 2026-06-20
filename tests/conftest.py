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
