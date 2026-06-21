"""Fixes surfaced by real-corpus (law-example) dogfooding: NFC paths, start_date as a
real column, language auto-detect, filename-searchable FTS."""
import unicodedata

import pytest


class _FakeTextStream:
    def __init__(self):
        self.kwargs = None

    def reconfigure(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def _mkpdf(path, text):
    from fpdf import FPDF

    p = FPDF()
    p.add_page()
    p.set_font("Helvetica", size=12)
    p.multi_cell(0, 8, text)
    p.output(str(path))


def test_cli_forces_utf8_stdio(monkeypatch):
    from dnr import cli

    out = _FakeTextStream()
    err = _FakeTextStream()
    monkeypatch.setattr(cli.sys, "stdout", out)
    monkeypatch.setattr(cli.sys, "stderr", err)

    cli._configure_utf8_stdio()

    assert out.kwargs == {"encoding": "utf-8"}
    assert err.kwargs == {"encoding": "utf-8"}


def test_nfc_path_query(tmp_path):
    """A file whose name is NFD on disk is stored/queried as NFC (macOS gotcha)."""
    from dnr import index, ingest

    folder = tmp_path / "nfd"
    folder.mkdir()
    p = folder / unicodedata.normalize("NFD", "가압류신청.pdf")
    _mkpdf(p, "body")
    ingest.record_supplied(p, "유체동산 가압류 신청", "vision", "agent", lang="ko")
    index.scan(folder)
    rows = index.query_where(folder, "path LIKE '%가압류%'")  # NFC literal in code
    assert len(rows) == 1
    assert rows[0]["path"] == unicodedata.normalize("NFC", rows[0]["path"])


def test_start_date_is_a_real_column(tmp_path):
    from dnr import index, ingest

    folder = tmp_path / "d"
    folder.mkdir()
    for name, sd in [("a.pdf", "2024-01-01"), ("b.pdf", "2026-05-10"), ("c.pdf", "2025-03-03")]:
        p = folder / name
        _mkpdf(p, "x")
        ingest.record_supplied(p, "body", "vision", "agent", fields={"start_date": sd, "title": name})
    index.scan(folder)
    rows = index.query_where(folder, "start_date >= '2026-01-01'")  # no json_extract needed
    assert {r["path"] for r in rows} == {"b.pdf"}
    assert [r["path"] for r in index.list_all(folder, sort="date")] == ["a.pdf", "c.pdf", "b.pdf"]


def test_lang_autodetect():
    from dnr import transcribe

    assert transcribe.detect_lang("이것은 한국어 계약서이며 손해배상 조항을 포함한다") == "ko"
    assert transcribe.detect_lang("This is an English contract with a damages clause") == "en"
    assert transcribe.detect_lang("これは日本語のテキストです") == "ja"


def test_verify_finds_db_only_record(tmp_path, capsys):
    """`dnr verify` must report a db-only/--no-embed record, not a misleading 'no dnr record'."""
    from dnr import cli, ingest

    p = tmp_path / "evidence.pdf"
    _mkpdf(p, "body")
    ingest.record_supplied(p, "그 전사 내용", no_embed=True)  # db-only (original byte-identical)
    assert cli.main(["verify", str(p)]) == 0
    assert "record: yes (db-only)" in capsys.readouterr().out


def test_coverage_reports_expensive_cache_gaps(tmp_path):
    """status/coverage: counts un-transcribed files by cost so agents see cache gaps."""
    from dnr import index, ingest

    folder = tmp_path / "c"
    folder.mkdir()
    txt = folder / "memo.txt"
    txt.write_text("이미 텍스트라 전사 불필요", encoding="utf-8")
    ingest.ingest(txt)                       # covered (cheap)
    _mkpdf(folder / "doc.pdf", "x")          # un-transcribed PDF -> parse
    (folder / "scan.png").write_bytes(b"x")  # un-transcribed image -> model

    c = index.coverage(folder)
    assert c["total"] == 3
    assert c["recorded"] == 1
    assert c["pending_model"] == 1 and c["pending_parse"] == 1
    assert c["should_offer_transcribe"] is True


def test_coverage_counts_usable_not_low_quality(tmp_path):
    from dnr import index, ingest

    folder = tmp_path / "quality"
    folder.mkdir()
    txt = folder / "memo.txt"
    txt.write_text("이미 텍스트라 전사 불필요", encoding="utf-8")
    _mkpdf(folder / "bad.pdf", "x")
    ingest.record_supplied(folder / "bad.pdf", "Ã¬ÂÂ Ã«Â¬Â´Ã¬Â²Â­ Â°Â¡Â¾Ð")
    index.scan(folder)

    c = index.coverage(folder)
    assert c["total"] == 2
    assert c["recorded"] == 2
    assert c["usable"] == 1
    assert c["needs_repair"] == 1
    assert c["repair_parse"] == 1
    assert c["repair_list"][0]["path"] == "bad.pdf"


def test_open_db_sets_busy_timeout(tmp_path):
    from dnr import index

    folder = tmp_path / "db"
    folder.mkdir()
    con = index.open_db(folder)
    try:
        assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        con.close()


def test_filename_is_searchable(tmp_path):
    """A term in the filename (not the body) is found via FTS over the name column."""
    from PIL import Image

    from dnr import index, ingest

    folder = tmp_path / "f"
    folder.mkdir()
    p = folder / "한정승인_관련_메모.png"  # an indexed (recorded) file; term only in the name
    Image.new("RGB", (20, 20), (1, 2, 3)).save(p)
    ingest.record_supplied(p, "body text without that term")
    index.scan(folder)
    assert index.query_match(folder, "한정승인") == ["한정승인_관련_메모.png"]
