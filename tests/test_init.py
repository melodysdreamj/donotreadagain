import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def test_init_creates_skill_and_key(tmp_path):
    from dnr import cli, keyring, skill

    d = tmp_path / "proj"
    assert cli.main(["init", str(d)]) == 0
    agents = d / "AGENTS.md"
    assert agents.exists()
    text = agents.read_text()
    assert skill.BEGIN in text and skill.END in text
    assert "dnr read" in text and "dnr query" in text
    # signing key was created
    assert (keyring.home() / "keys" / "default.ed25519").exists()


def test_init_idempotent(tmp_path):
    from dnr import cli, skill

    d = tmp_path / "proj"
    cli.main(["init", str(d)])
    cli.main(["init", str(d)])
    text = (d / "AGENTS.md").read_text()
    assert text.count(skill.BEGIN) == 1  # block replaced, not duplicated


def test_init_preserves_existing(tmp_path):
    from dnr import cli

    d = tmp_path / "proj"
    d.mkdir()
    (d / "AGENTS.md").write_text("# My project\n\nExisting house rules.\n")
    cli.main(["init", str(d)])
    text = (d / "AGENTS.md").read_text()
    assert "Existing house rules." in text and "dnr read" in text


def test_init_updates_existing_surfaces(tmp_path):
    from dnr import cli, skill

    d = tmp_path / "proj"
    d.mkdir()
    (d / "CLAUDE.md").write_text("# Claude rules\n")
    cli.main(["init", str(d)])
    # updates the existing CLAUDE.md rather than creating AGENTS.md
    assert skill.BEGIN in (d / "CLAUDE.md").read_text()
    assert not (d / "AGENTS.md").exists()
