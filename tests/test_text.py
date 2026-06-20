"""Non-PDF routing fixes (from multi-user dogfood): text files work, visual/unknown
types give clean errors instead of pypdf crashes."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def test_ingest_txt_as_sidecar(tmp_path):
    from dnr import embed, hashing, ingest

    p = tmp_path / "notes.txt"
    p.write_text("meeting notes: project alpha deadline friday", encoding="utf-8")
    rec = ingest.ingest(p)
    assert rec["provenance"]["method"] == "none"
    assert rec["content_hash"] == hashing.content_hash(p)
    assert embed.extract_sidecar(p) == rec  # txt has no in-file slot -> sidecar
    assert ingest.read_cached(p) is not None


def test_text_files_indexed_and_searchable(tmp_path):
    from dnr import index, ingest

    folder = tmp_path / "c"
    folder.mkdir()
    (folder / "a.txt").write_text("alpha banana cherry", encoding="utf-8")
    (folder / "b.md").write_text("delta echo foxtrot", encoding="utf-8")
    ingest.ingest(folder / "a.txt")
    ingest.ingest(folder / "b.md")
    stats = index.scan(folder)
    assert stats["indexed"] == 2
    assert index.query_match(folder, "banana") == ["a.txt"]


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
