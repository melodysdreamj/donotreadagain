import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DNR_HOME", str(tmp_path / "dnrhome"))


def test_init_ensures_key_and_writes_no_folder_note(tmp_path):
    """`dnr init` sets up a signing key and installs NO per-folder note."""
    from dnr import cli, keyring

    d = tmp_path / "proj"
    d.mkdir()
    assert cli.main(["init"]) == 0
    assert (keyring.home() / "keys" / "default.ed25519").exists()
    # the whole point: no per-folder stanza is dropped anywhere
    assert not (d / "AGENTS.md").exists()
    assert not (d / "CLAUDE.md").exists()


def test_skill_md_is_fetchable_skill(tmp_path, capsys):
    """`dnr skill` prints a SKILL.md (frontmatter + the decision flow) agents can fetch."""
    from dnr import cli, skill

    md = skill.skill_md()
    assert md.startswith("---\nname: dnr\n")
    assert "description:" in md.split("---", 2)[1]
    for marker in ("read once, never again", "## A. One specific file", "## B. A folder-wide question",
                   "permission gate", "uvx --from donotreadagain dnr"):
        assert marker in md
    assert cli.main(["skill"]) == 0
    assert "name: dnr" in capsys.readouterr().out


def test_record_self_describes_via_about(tmp_path):
    """Every record carries an `_about` pointer so the file advertises itself + the skill URL."""
    from dnr import bootstrap, record

    rec = record.new_record(
        content_hash="sha256:" + "0" * 64,
        source={"mime": "application/pdf"},
    )
    assert rec["_about"] == bootstrap.ABOUT
    assert "donotreadagain" in rec["_about"]
    assert bootstrap.SKILL_URL in rec["_about"]
    # signed/validated like any field (schema allows it)
    from dnr import schema
    assert schema.validate(rec) == []
