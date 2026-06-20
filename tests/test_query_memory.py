"""Query memory: composed queries (tag ∩ tag ∩ time ∩ text), saved/reusable queries, and
agent-accumulated tags via `dnr tag`."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def _rec(folder, name, text, date, tags):
    from fpdf import FPDF

    from dnr import ingest

    p = folder / name
    d = FPDF()
    d.add_page()
    d.set_font("Helvetica", size=12)
    d.cell(0, 8, "doc")  # ascii body; the (Korean) transcript is supplied to record
    d.output(str(p))
    ingest.record_supplied(p, text, fields={"start_date": date, "title": name}, tags=tags)
    return p


def test_compose_tag_time_text(tmp_path):
    from dnr import index

    f = tmp_path / "f"
    f.mkdir()
    _rec(f, "a.pdf", "가압류 신청 청구금액", "2025-07-20", ["가압류", "신청"])
    _rec(f, "b.pdf", "가압류 이의 담보", "2026-05-19", ["가압류", "결정"])
    _rec(f, "c.pdf", "불송치 증거불충분", "2026-02-12", ["형사"])
    index.scan(f)

    assert {x["path"] for x in index.query_compose(f, tags=["가압류"], since="2025-06-01")} == {"a.pdf", "b.pdf"}
    assert [x["path"] for x in index.query_compose(f, tags=["가압류"], match="담보")] == ["b.pdf"]
    assert [x["path"] for x in index.query_compose(f, tags=["가압류", "결정"])] == ["b.pdf"]
    assert [x["path"] for x in index.query_compose(f, tags=["가압류"], until="2025-12-31")] == ["a.pdf"]


def test_save_list_use_query(tmp_path):
    from dnr import index

    f = tmp_path / "f"
    f.mkdir()
    _rec(f, "a.pdf", "가압류", "2025-07-20", ["가압류"])
    index.scan(f)

    expr = {"tags": ["가압류"], "since": "2025-01-01", "sort": "date"}
    index.save_query(f, "최근가압류", expr)
    assert index.get_query(f, "최근가압류") == expr
    assert [q["label"] for q in index.list_queries(f)] == ["최근가압류"]
    index.log_query_run(f, "최근가압류", 1)
    row = index.list_queries(f)[0]
    assert row["run_count"] == 1 and row["last_hits"] == 1


def test_tag_add_remove_and_reindex(tmp_path):
    from dnr import index, ingest

    f = tmp_path / "f"
    f.mkdir()
    p = _rec(f, "a.pdf", "body", "2025-01-01", ["x"])
    index.scan(f)

    assert ingest.set_tags(p, add=["면탈", "가압류"]) == ["x", "면탈", "가압류"]
    assert ingest.set_tags(p, remove=["x"]) == ["면탈", "가압류"]
    assert ingest.current_tags(p) == ["면탈", "가압류"]
    # tagging a carrier file refreshes its index row immediately (no manual re-index)
    assert [r["path"] for r in index.query_compose(f, tags=["면탈"])] == ["a.pdf"]
