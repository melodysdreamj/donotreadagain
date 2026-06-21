import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def test_strip_removes_record_keeps_content(sample_pdf):
    from dnr import embed, hashing, ingest

    ingest.ingest(sample_pdf, embed=True)
    before = hashing.content_hash(sample_pdf)
    assert embed.extract(sample_pdf) is not None
    assert embed.strip(sample_pdf) is True
    assert embed.extract(sample_pdf) is None  # record gone
    assert hashing.content_hash(sample_pdf) == before  # content untouched


def test_cli_strip_removes_db_only_record(sample_pdf):
    from dnr import cli, ingest

    ingest.ingest(sample_pdf)
    assert ingest.read_cached(sample_pdf) is not None
    assert cli.main(["strip", str(sample_pdf)]) == 0
    assert ingest.read_cached(sample_pdf) is None


def test_strip_sidecar(sample_pdf):
    from dnr import embed

    embed.embed_sidecar(sample_pdf, {"dnr": "0.1"})
    assert embed.strip(sample_pdf) is True
    assert embed.extract_sidecar(sample_pdf) is None


def test_strip_nothing_to_remove(sample_pdf):
    from dnr import embed

    assert embed.strip(sample_pdf) is False
