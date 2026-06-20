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


@pytest.fixture
def corpus(tmp_path):
    from dnr import ingest

    folder = tmp_path / "corpus"
    folder.mkdir()
    a, b = folder / "a.pdf", folder / "b.pdf"
    _mkpdf(a, "Apple contract about damages and penalties")
    _mkpdf(b, "Banana lease agreement and rent")
    ingest.ingest(a)
    ingest.ingest(b)
    return folder


def test_index_and_query_where(corpus):
    from dnr import index

    stats = index.scan(corpus)
    assert stats["indexed"] == 2
    rows = index.query_where(corpus, "method = 'text-extract'")
    assert len(rows) == 2
    assert {r["path"] for r in rows} == {"a.pdf", "b.pdf"}


def test_index_fts_match(corpus):
    from dnr import index

    index.scan(corpus)
    hits = index.query_match(corpus, "damages")
    assert hits == ["a.pdf"]


def test_index_incremental_skips(corpus):
    from dnr import index

    index.scan(corpus)
    stats = index.scan(corpus)  # nothing changed
    assert stats["indexed"] == 0 and stats["skipped"] == 2


def test_index_move_resilience(corpus):
    from dnr import index

    index.scan(corpus)
    sub = corpus / "sub"
    sub.mkdir()
    (corpus / "a.pdf").rename(sub / "a.pdf")
    stats = index.scan(corpus)
    assert stats["moved"] == 1 and stats["indexed"] == 0 and stats["removed"] == 0
    paths = {r["path"] for r in index.query_where(corpus, "1=1")}
    assert "sub/a.pdf" in paths and "a.pdf" not in paths


def test_index_tombstone(corpus):
    from dnr import index

    index.scan(corpus)
    (corpus / "b.pdf").unlink()
    stats = index.scan(corpus)
    assert stats["removed"] == 1
    assert {r["path"] for r in index.query_where(corpus, "1=1")} == {"a.pdf"}


def test_index_cjk_fts(tmp_path):
    """Korean full-text search via the trigram tokenizer (M6)."""
    from dnr import index, ingest

    folder = tmp_path / "kr"
    folder.mkdir()
    doc = folder / "judgment.pdf"
    _mkpdf(doc, "placeholder")  # body text is irrelevant; transcript is supplied
    ingest.record_supplied(doc, "계약 위반에 따른 손해배상 책임을 인정한다.", "vision", "agent", lang="ko")
    index.scan(folder)
    assert index.query_match(folder, "손해배상") == ["judgment.pdf"]
    assert index.query_where(folder, "lang = 'ko'")[0]["path"] == "judgment.pdf"
