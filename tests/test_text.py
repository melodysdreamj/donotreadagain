"""Non-PDF routing fixes (from multi-user dogfood): text files work, visual/unknown
types give clean errors instead of pypdf crashes."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def test_ingest_txt_makes_no_record(tmp_path):
    """Already-readable text needs no transcription and no record — agents read it directly."""
    from dnr import ingest

    p = tmp_path / "notes.txt"
    p.write_text("meeting notes: project alpha deadline friday", encoding="utf-8")
    assert ingest.ingest(p) is None              # no record produced
    assert not (tmp_path / "notes.txt.dnr.json").exists()  # no sidecar
    assert ingest.read_cached(p) is None         # nothing cached -> read the file directly


def test_text_not_indexed(tmp_path):
    """Text isn't put in the dnr index (it's read directly); ingesting it is a no-op."""
    from dnr import index, ingest

    folder = tmp_path / "c"
    folder.mkdir()
    (folder / "a.txt").write_text("alpha banana cherry", encoding="utf-8")
    assert ingest.ingest(folder / "a.txt") is None
    index.scan(folder)
    assert index.query_match(folder, "banana") == []  # text is not a dnr record


def test_ingest_image_clean_error(tmp_path):
    from dnr import cli

    p = tmp_path / "scan.png"
    p.write_bytes(b"\x89PNG\r\n not really")
    assert cli.main(["ingest", str(p)]) == 1  # clean 'use dnr record', no pypdf crash


def test_ingest_unsupported_clean_error(tmp_path):
    from dnr import cli

    p = tmp_path / "x.xyz"
    p.write_bytes(b"data")
    assert cli.main(["ingest", str(p)]) == 1
