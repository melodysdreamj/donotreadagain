"""Robustness fixes from M9 dogfooding: corrupt / missing files must not crash."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def _mkpdf(path, text):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, text)
    pdf.output(str(path))


def test_ingest_corrupt_file_clean_error(tmp_path):
    from dnr import cli

    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf at all")
    rc = cli.main(["ingest", str(bad)])
    assert rc == 1  # clean nonzero exit, not an unhandled traceback


def test_index_skips_corrupt_keeps_good(tmp_path):
    from dnr import index, ingest

    folder = tmp_path / "c"
    folder.mkdir()
    (folder / "bad.pdf").write_bytes(b"garbage not pdf")
    good = folder / "good.pdf"
    _mkpdf(good, "perfectly good content here")
    ingest.ingest(good)

    stats = index.scan(folder)  # must not abort on the corrupt file
    assert stats["indexed"] == 1
    paths = {r["path"] for r in index.query_where(folder, "1=1")}
    assert "good.pdf" in paths


def test_read_missing_file_falls_back(tmp_path):
    from dnr import cli, ingest

    missing = tmp_path / "nope.pdf"
    assert ingest.read_cached(missing) is None
    assert cli.main(["read", str(missing)]) == 0  # clean fallback, no crash


def test_read_corrupt_file_falls_back(tmp_path):
    from dnr import ingest

    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"definitely not a pdf")
    assert ingest.read_cached(bad) is None
