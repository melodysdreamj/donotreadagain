import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """Keep the signing key under a tmp DNR_HOME for every test here."""
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def test_ingest_text_extract(sample_pdf):
    from dnr import embed, hashing, ingest, keyring, signing

    rec = ingest.ingest(sample_pdf, transcriber="text-extract")
    assert rec["provenance"]["method"] == "text-extract"
    assert rec["content_hash"] == hashing.content_hash(sample_pdf)
    assert "sig" in rec
    # the embedded record round-trips and verifies against our own key
    got = embed.extract(sample_pdf)
    assert got == rec
    assert signing.verify(got, keyring.default_trust())


def test_ingest_is_idempotent_no_drift(sample_pdf):
    from dnr import hashing, ingest

    ingest.ingest(sample_pdf, transcriber="text-extract")
    w1 = hashing.whole_hash(sample_pdf)
    ingest.ingest(sample_pdf, transcriber="text-extract")
    w2 = hashing.whole_hash(sample_pdf)
    assert w1 == w2  # same content + model → byte-identical record (gate 4)


def test_read_cached_hit(sample_pdf):
    from dnr import ingest

    ingest.ingest(sample_pdf, transcriber="text-extract")
    assert ingest.read_cached(sample_pdf) is not None


def test_read_cached_miss_on_unsigned(sample_pdf):
    from dnr import embed, ingest

    embed.embed(sample_pdf, {"dnr": "0.1", "content_hash": "sha256:x",
                             "transcript": {"text": "forged"}})
    assert ingest.read_cached(sample_pdf) is None  # untrusted → fall back


def test_record_supplied_agent_path(sample_pdf):
    from dnr import ingest

    body = "# Verbatim\nThe full body text, supplied by the agent."
    rec = ingest.record_supplied(sample_pdf, body, "vision", "claude-opus-4-vision")
    assert rec["provenance"]["transcriber"] == "claude-opus-4-vision"
    assert ingest.read_cached(sample_pdf) == body


def test_cli_smoke(sample_pdf):
    from dnr import cli

    assert cli.main(["keygen"]) == 0
    assert cli.main(["ingest", str(sample_pdf)]) == 0
    assert cli.main(["verify", str(sample_pdf)]) == 0
    assert cli.main(["read", str(sample_pdf)]) == 0
