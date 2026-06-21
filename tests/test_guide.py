def test_prompt_hash_deterministic():
    from dnr import guide

    assert guide.prompt_hash() == guide.prompt_hash()
    assert guide.prompt_hash().startswith("sha256:")


def test_guide_is_strict_verbatim():
    from dnr import guide

    text = guide.GUIDE.lower()
    assert "verbatim" in text
    assert "do not summarize" in text or "not summarize" in text


def test_provenance_stamp_shape():
    from dnr import guide

    p = guide.provenance_stamp("vision", "claude-opus-4-vision")
    assert p["method"] == "vision"
    assert p["transcriber"] == "claude-opus-4-vision"
    assert p["instruction_id"] == guide.INSTRUCTION_ID
    assert p["prompt_hash"].startswith("sha256:")


def test_formats_matrix_render():
    from dnr import formats

    out = formats.render()
    assert ".pdf" in out and ".mp3" in out and ".xlsx" in out
    assert "PyMuPDF" in out and "openpyxl" in out and "asr (Whisper" in out
    assert all(s in {"implemented", "partial", "planned", "n/a"}
               for *_, s in formats.SUPPORTED.values())
