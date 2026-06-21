"""Dogfood-driven query fixes: explicit (never-inferred) dates, comma-insensitive number search,
content_hash dedup, and a min-chars (low-quality transcript) filter."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def _mkpdf(path, body="doc"):
    from fpdf import FPDF

    p = FPDF()
    p.add_page()
    p.set_font("Helvetica", size=12)
    p.cell(0, 8, body)
    p.output(str(path))


def test_explicit_date_then_filter(tmp_path):
    """Dates are optional and never inferred — set one explicitly, then --since/--until apply."""
    from dnr import index, ingest

    f = tmp_path / "f"
    f.mkdir()
    p = f / "a.pdf"
    _mkpdf(p)
    ingest.record_supplied(p, "가압류 결정")
    index.scan(f)

    assert index.query_compose(f, since="2026-01-01") == []   # no date yet -> excluded
    assert ingest.set_date(p, "2026-05-19") == "2026-05-19"
    assert ingest.current_date(p) == "2026-05-19"
    assert [r["path"] for r in index.query_compose(f, since="2026-05-01", until="2026-05-31")] == ["a.pdf"]


def test_number_comma_insensitive_match(tmp_path):
    from dnr import index, ingest

    f = tmp_path / "f"
    f.mkdir()
    p = f / "a.pdf"
    _mkpdf(p)
    ingest.record_supplied(p, "피보전채권 총액 3,681,520,202원")
    index.scan(f)

    assert [r["path"] for r in index.query_compose(f, match="3681520202")] == ["a.pdf"]      # no commas
    assert [r["path"] for r in index.query_compose(f, match="3,681,520,202")] == ["a.pdf"]   # with commas


def test_dedup_by_content_hash(tmp_path):
    import shutil

    from dnr import index, ingest

    f = tmp_path / "f"
    f.mkdir()
    _mkpdf(f / "a.pdf")
    shutil.copyfile(f / "a.pdf", f / "b.pdf")  # identical bytes -> identical content_hash
    ingest.record_supplied(f / "a.pdf", "same body text")
    ingest.record_supplied(f / "b.pdf", "same body text")
    index.scan(f)

    assert len(index.query_compose(f, match="same")) == 2
    assert len(index.query_compose(f, match="same", dedup=True)) == 1


def test_min_chars_filters_low_density(tmp_path):
    from dnr import index, ingest

    f = tmp_path / "f"
    f.mkdir()
    _mkpdf(f / "full.pdf")
    _mkpdf(f / "thin.pdf")
    ingest.record_supplied(f / "full.pdf", "x" * 300)
    ingest.record_supplied(f / "thin.pdf", "y")
    index.scan(f)

    assert {r["path"] for r in index.query_compose(f, min_chars=100)} == {"full.pdf"}


def test_any_terms_or(tmp_path):
    """--any does a synonym sweep — match ANY of the terms (helps "빠짐없이")."""
    from dnr import index, ingest

    f = tmp_path / "f"
    f.mkdir()
    _mkpdf(f / "a.pdf")
    _mkpdf(f / "b.pdf")
    _mkpdf(f / "c.pdf")
    ingest.record_supplied(f / "a.pdf", "유체동산 가압류 신청")
    ingest.record_supplied(f / "b.pdf", "보전처분 피보전권리")
    ingest.record_supplied(f / "c.pdf", "불송치 증거불충분")
    index.scan(f)

    assert {r["path"] for r in index.query_compose(f, any_terms=["가압류", "보전"])} == {"a.pdf", "b.pdf"}


def test_any_tags_or(tmp_path):
    from dnr import index, ingest

    f = tmp_path / "f"
    f.mkdir()
    _mkpdf(f / "a.pdf")
    _mkpdf(f / "b.pdf")
    _mkpdf(f / "c.pdf")
    ingest.record_supplied(f / "a.pdf", "body", tags=["우리측"])
    ingest.record_supplied(f / "b.pdf", "body", tags=["상대측"])
    ingest.record_supplied(f / "c.pdf", "body", tags=["기타"])
    index.scan(f)

    assert {r["path"] for r in index.query_compose(f, any_tags=["우리측", "상대측"])} == {"a.pdf", "b.pdf"}


def test_low_quality_heuristic_and_records(tmp_path):
    from dnr import index, ingest, transcribe

    assert transcribe.is_low_quality("") is True
    assert transcribe.is_low_quality("가압류 신청서 청구금액 1000만원입니다") is False
    assert transcribe.is_low_quality("A normal English contract clause, section 3.") is False
    assert transcribe.is_low_quality("Ã¬ÂÂ Ã«Â¬Â´Ã¬Â²Â­ Â°Â¡Â¾Ð Ã¬ÂÂ Ã«Â²Â½ Â¹Â®Ã¬ÂÂ") is True  # mojibake

    f = tmp_path / "f"
    f.mkdir()
    _mkpdf(f / "good.pdf")
    _mkpdf(f / "bad.pdf")
    ingest.record_supplied(f / "good.pdf", "정상적인 한국어 전사 내용 가압류 청구금액 일천만원")
    ingest.record_supplied(f / "bad.pdf", "Ã¬ÂÂ Ã«Â¬Â´Ã¬Â²Â­ Â°Â¡Â¾Ð Ã¬ÂÂ Ã«Â²Â½ Â¹Â®Ã¬ÂÂ")
    index.scan(f)
    lq = index.low_quality_records(f)
    assert "bad.pdf" in lq and "good.pdf" not in lq
