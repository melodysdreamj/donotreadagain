from dnr import hashing


def test_content_hash_deterministic(sample_pdf):
    assert hashing.content_hash(sample_pdf) == hashing.content_hash(sample_pdf)


def test_pdf_hash_has_prefix(sample_pdf):
    assert hashing.content_hash(sample_pdf).startswith("sha256:")


def test_whole_vs_content_differ(sample_pdf):
    assert hashing.whole_hash(sample_pdf) != hashing.content_hash(sample_pdf)


def test_wav_content_hash(sample_wav):
    assert hashing.content_hash(sample_wav).startswith("sha256:")


def test_mp3_content_hash_skips_id3(sample_mp3):
    # adding an ID3v2 tag at the front must not change the audio-frame hash
    before = hashing.content_hash(sample_mp3)
    from mutagen.id3 import ID3, TXXX

    tags = ID3()
    tags.add(TXXX(encoding=3, desc="x", text=["y" * 500]))
    tags.save(str(sample_mp3))
    assert hashing.content_hash(sample_mp3) == before


def test_unsupported_extension(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"\x00")
    try:
        hashing.content_hash(p)
        assert False, "expected ValueError"
    except ValueError:
        pass
