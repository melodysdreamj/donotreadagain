import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def test_real_record_validates(sample_pdf):
    from dnr import embed, ingest, schema

    ingest.ingest(sample_pdf)
    rec = embed.extract(sample_pdf)
    assert schema.validate(rec) == []


def test_invalid_record_reports_errors():
    from dnr import schema

    errors = schema.validate({"content_hash": "sha256:x"})  # missing dnr+source, bad hash
    assert errors  # non-empty list of messages


def test_forged_hash_rejected_by_schema():
    from dnr import schema

    rec = {"dnr": "0.1", "content_hash": "sha256:x", "source": {"mime": "application/pdf"}}
    assert any("content_hash" in e for e in schema.validate(rec))


def test_cli_validate_and_schema(sample_pdf):
    from dnr import cli, ingest

    ingest.ingest(sample_pdf)
    assert cli.main(["validate", str(sample_pdf)]) == 0
    assert cli.main(["schema"]) == 0
