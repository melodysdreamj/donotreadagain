"""Format coverage: images (content_hash + agent record + sidecar) and docx (local extract)."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def _mkpng(path):
    from PIL import Image

    im = Image.new("RGB", (40, 30))
    for x in range(40):
        for y in range(30):
            im.putpixel((x, y), ((x * 6) % 256, (y * 8) % 256, 120))
    im.save(path)


def test_image_content_hash_stable(tmp_path):
    from dnr import hashing

    p = tmp_path / "a.png"
    _mkpng(p)
    assert hashing.content_hash(p) == hashing.content_hash(p)
    assert hashing.content_hash(p).startswith("sha256:")


def test_image_record_and_search(tmp_path):
    from dnr import embed, index, ingest

    folder = tmp_path / "img"
    folder.mkdir()
    p = folder / "chart.png"
    _mkpng(p)
    rec = ingest.record_supplied(p, "Bar chart: Q4 revenue 1,200,000 KRW by region", "vision", "claude-opus-4-vision")
    assert rec["provenance"]["method"] == "vision"
    assert embed.extract_sidecar(p) == rec  # image -> sidecar, file untouched
    index.scan(folder)
    assert index.query_match(folder, "revenue") == ["chart.png"]


def test_image_ingest_directs_to_record(tmp_path):
    from dnr import cli

    p = tmp_path / "x.png"
    _mkpng(p)
    assert cli.main(["ingest", str(p)]) == 1  # clean 'use dnr record', no crash


def test_docx_ingest_local(tmp_path):
    import docx

    from dnr import embed, hashing, index, ingest

    folder = tmp_path / "d"
    folder.mkdir()
    p = folder / "memo.docx"
    d = docx.Document()
    d.add_paragraph("Quarterly memo: contract renewal pending approval")
    d.save(str(p))
    rec = ingest.ingest(p)
    assert rec["provenance"]["transcriber"] == "python-docx"
    assert rec["content_hash"] == hashing.content_hash(p)
    assert embed.extract_sidecar(p) == rec
    index.scan(folder)
    assert index.query_match(folder, "renewal") == ["memo.docx"]


def test_docx_bytes_unchanged_by_ingest(tmp_path):
    import docx

    from dnr import hashing, ingest

    p = tmp_path / "m.docx"
    d = docx.Document()
    d.add_paragraph("body text")
    d.save(str(p))
    h0 = hashing.content_hash(p)
    ingest.ingest(p)  # writes a sidecar; the .docx zip is not touched
    assert hashing.content_hash(p) == h0
