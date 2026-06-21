"""Conformance gates (vision.md §16):
  1. content_hash unchanged after embed
  2. native tags preserved
  4. re-embed is byte-deterministic (whole_hash stable)
"""
from dnr import embed, hashing


def test_sidecar_roundtrip(sample_pdf, sample_record):
    embed.embed_sidecar(sample_pdf, sample_record)
    assert embed.extract_sidecar(sample_pdf) == sample_record


def test_pdf_gate1_content_hash_invariant(sample_pdf, sample_record):
    h0 = hashing.content_hash(sample_pdf)
    embed.embed_pdf(sample_pdf, sample_record)
    assert hashing.content_hash(sample_pdf) == h0


def test_pdf_roundtrip(sample_pdf, sample_record):
    embed.embed_pdf(sample_pdf, sample_record)
    assert embed.extract_pdf(sample_pdf) == sample_record


def test_pdf_gate2_native_tag_preserved(sample_pdf, sample_record):
    import pikepdf

    with pikepdf.open(sample_pdf, allow_overwriting_input=True) as pdf:
        with pdf.open_metadata() as m:
            m["dc:title"] = "KEEPME"
        pdf.save(sample_pdf)
    embed.embed_pdf(sample_pdf, sample_record)
    with pikepdf.open(sample_pdf) as pdf:
        with pdf.open_metadata() as m:
            assert m.get("dc:title") == "KEEPME"


def test_pdf_gate4_reembed_deterministic(sample_pdf, sample_record):
    embed.embed_pdf(sample_pdf, sample_record)
    w1 = hashing.whole_hash(sample_pdf)
    embed.embed_pdf(sample_pdf, sample_record)
    w2 = hashing.whole_hash(sample_pdf)
    assert w1 == w2


def test_mp3_gate1_content_hash_invariant(sample_mp3, sample_record):
    h0 = hashing.content_hash(sample_mp3)
    embed.embed_mp3(sample_mp3, sample_record)
    assert hashing.content_hash(sample_mp3) == h0


def test_mp3_roundtrip(sample_mp3, sample_record):
    embed.embed_mp3(sample_mp3, sample_record)
    assert embed.extract_mp3(sample_mp3) == sample_record


def test_m4a_gate1_content_hash_invariant(sample_m4a, sample_record):
    h0 = hashing.content_hash(sample_m4a)
    embed.embed_mp4(sample_m4a, sample_record)
    assert hashing.content_hash(sample_m4a) == h0


def test_m4a_roundtrip(sample_m4a, sample_record):
    embed.embed_mp4(sample_m4a, sample_record)
    assert embed.extract_mp4(sample_m4a) == sample_record


def test_flac_gate1_content_hash_invariant(sample_flac, sample_record):
    h0 = hashing.content_hash(sample_flac)
    embed.embed_flac(sample_flac, sample_record)
    assert hashing.content_hash(sample_flac) == h0


def test_flac_roundtrip(sample_flac, sample_record):
    embed.embed_flac(sample_flac, sample_record)
    assert embed.extract_flac(sample_flac) == sample_record


def test_ogg_gate1_content_hash_invariant(sample_ogg, sample_record):
    h0 = hashing.content_hash(sample_ogg)
    embed.embed_ogg(sample_ogg, sample_record)
    assert hashing.content_hash(sample_ogg) == h0


def test_ogg_roundtrip(sample_ogg, sample_record):
    embed.embed_ogg(sample_ogg, sample_record)
    assert embed.extract_ogg(sample_ogg) == sample_record


def test_opus_gate1_content_hash_invariant(sample_opus, sample_record):
    h0 = hashing.content_hash(sample_opus)
    embed.embed_ogg(sample_opus, sample_record)
    assert hashing.content_hash(sample_opus) == h0


def test_opus_roundtrip(sample_opus, sample_record):
    embed.embed_ogg(sample_opus, sample_record)
    assert embed.extract_ogg(sample_opus) == sample_record


def test_mp4_roundtrip(sample_mp4, sample_record):
    embed.embed(sample_mp4, sample_record)
    assert embed.extract(sample_mp4) == sample_record


def test_mp4_strip(sample_mp4, sample_record):
    h0 = hashing.content_hash(sample_mp4)
    embed.embed(sample_mp4, sample_record)
    assert embed.strip(sample_mp4)
    assert embed.extract(sample_mp4) is None
    assert hashing.content_hash(sample_mp4) == h0


def test_dispatch_extract(sample_pdf, sample_record):
    embed.embed(sample_pdf, sample_record)
    assert embed.extract(sample_pdf) == sample_record
