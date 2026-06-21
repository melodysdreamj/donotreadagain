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


def test_m4a_content_hash_skips_freeform_metadata(sample_m4a):
    before = hashing.content_hash(sample_m4a)
    from mutagen.mp4 import MP4, MP4FreeForm

    tags = MP4(sample_m4a)
    if tags.tags is None:
        tags.add_tags()
    tags.tags["----:com.example:test"] = [MP4FreeForm(b"metadata", dataformat=1)]
    tags.save()
    assert hashing.content_hash(sample_m4a) == before


def test_flac_content_hash_skips_vorbis_comment(sample_flac):
    before = hashing.content_hash(sample_flac)
    from mutagen.flac import FLAC

    tags = FLAC(sample_flac)
    if tags.tags is None:
        tags.add_tags()
    tags["COMMENT"] = ["metadata"]
    tags.save()
    assert hashing.content_hash(sample_flac) == before


def test_ogg_content_hash_skips_vorbis_comment(sample_ogg):
    before = hashing.content_hash(sample_ogg)
    from mutagen.oggvorbis import OggVorbis

    tags = OggVorbis(sample_ogg)
    tags["COMMENT"] = ["metadata"]
    tags.save()
    assert hashing.content_hash(sample_ogg) == before


def test_opus_content_hash_skips_tags(sample_opus):
    before = hashing.content_hash(sample_opus)
    from mutagen.oggopus import OggOpus

    tags = OggOpus(sample_opus)
    tags["COMMENT"] = ["metadata"]
    tags.save()
    assert hashing.content_hash(sample_opus) == before


def test_mp4_content_hash_has_prefix(sample_mp4):
    assert hashing.content_hash(sample_mp4).startswith("sha256:")


def test_unsupported_extension(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"\x00")
    try:
        hashing.content_hash(p)
        assert False, "expected ValueError"
    except ValueError:
        pass
