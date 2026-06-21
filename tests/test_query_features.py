"""Query surface: tag filter, sort (incl. time/date), and keyword ±N context (KWIC)."""
import pytest


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


def test_query_by_tag(tmp_path):
    from dnr import index, ingest

    folder = tmp_path / "c"
    folder.mkdir()
    a, b = folder / "a.pdf", folder / "b.pdf"
    _mkpdf(a, "alpha")
    _mkpdf(b, "beta")
    ingest.record_supplied(a, "alpha contract body", "vision", "agent", tags=["legal", "contract"])
    ingest.record_supplied(b, "beta invoice body", "vision", "agent", tags=["finance"])
    index.scan(folder)
    assert {r["path"] for r in index.query_tag(folder, "legal")} == {"a.pdf"}
    assert {r["path"] for r in index.query_tag(folder, "finance")} == {"b.pdf"}
    assert index.query_tag(folder, "nope") == []


def test_query_sort(tmp_path):
    from dnr import index, ingest

    folder = tmp_path / "c"
    folder.mkdir()
    for name, title in [("a.pdf", "Zebra"), ("b.pdf", "Apple"), ("c.pdf", "Mango")]:
        p = folder / name
        _mkpdf(p, "x")
        ingest.record_supplied(p, "body", "vision", "agent", fields={"title": title})
    index.scan(folder)
    assert [r["title"] for r in index.list_all(folder, sort="title")] == ["Apple", "Mango", "Zebra"]
    assert [r["title"] for r in index.list_all(folder, sort="title", desc=True)] == ["Zebra", "Mango", "Apple"]


def test_keyword_context_kwic(tmp_path):
    from dnr import index, ingest

    folder = tmp_path / "c"
    folder.mkdir()
    p = folder / "doc.pdf"
    _mkpdf(p, "x")
    body = "A" * 300 + " the party shall pay damages of one million KRW " + "B" * 300
    ingest.record_supplied(p, body, "vision", "agent")
    index.scan(folder)
    results = index.search_context(folder, "damages", radius=20)
    assert len(results) == 1
    path, snips = results[0]
    assert path == "doc.pdf"
    assert len(snips) == 1
    assert "damages" in snips[0]
    assert snips[0].startswith("…") and snips[0].endswith("…")  # windowed on both sides
    assert len(snips[0]) < 120  # ~±20 chars, not the whole body


def test_cli_query_features(tmp_path, capsys):
    from dnr import cli, index, ingest

    folder = tmp_path / "c"
    folder.mkdir()
    p = folder / "a.pdf"
    _mkpdf(p, "x")
    ingest.record_supplied(p, "the contract mentions damages clearly", "vision", "agent", tags=["legal"])
    index.scan(folder)
    assert cli.main(["query", str(folder), "--tag", "legal"]) == 0
    assert cli.main(["query", str(folder), "--match", "damages", "--context", "30"]) == 0
    out = capsys.readouterr().out
    assert "damages" in out
    assert cli.main(["query", str(folder), "--list", "--sort", "mtime", "--desc"]) == 0


def test_cli_context_with_tag_filter(tmp_path, capsys):
    from dnr import cli, index, ingest

    folder = tmp_path / "c"
    folder.mkdir()
    p = folder / "a.pdf"
    _mkpdf(p, "x")
    ingest.record_supplied(p, "aaa 표현대리 bbb", "vision", "agent", tags=["법정제출"])
    index.scan(folder)

    assert cli.main(["query", str(folder), "--tag", "법정제출", "--match", "표현대리", "--context", "5"]) == 0
    out = capsys.readouterr().out
    assert "a.pdf" in out and "표현대리" in out
