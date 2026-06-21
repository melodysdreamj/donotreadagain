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


def test_init_prints_agent_contract_hint(capsys):
    from dnr import cli

    assert cli.main(["init"]) == 0
    out = capsys.readouterr().out
    assert "tell your agent: Use dnr for this folder." in out
    assert "agent contract: dnr read before parsing" in out
    assert "cache expensive misses with dnr ingest/record" in out


def test_init_can_add_agent_file_bootstrap(tmp_path, monkeypatch, capsys):
    from dnr import bootstrap, cli

    monkeypatch.chdir(tmp_path)
    assert cli.main(["init", "--agent-file", "AGENTS.md"]) == 0
    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert text == bootstrap.AGENT_BOOTSTRAP + "\n"
    assert "created agent bootstrap in AGENTS.md" in capsys.readouterr().out

    assert cli.main(["init", "--agent-file", "AGENTS.md"]) == 0
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == text
    assert "unchanged agent bootstrap in AGENTS.md" in capsys.readouterr().out


def test_init_appends_agent_file_bootstrap(tmp_path, monkeypatch):
    from dnr import bootstrap, cli

    monkeypatch.chdir(tmp_path)
    p = tmp_path / "CLAUDE.md"
    p.write_text("# Existing notes\n", encoding="utf-8")
    assert cli.main(["init", "--agent-file", "CLAUDE.md"]) == 0
    assert p.read_text(encoding="utf-8") == "# Existing notes\n\n" + bootstrap.AGENT_BOOTSTRAP + "\n"


def test_init_upgrades_legacy_agent_file_bootstrap(tmp_path, monkeypatch):
    from dnr import bootstrap, cli

    monkeypatch.chdir(tmp_path)
    p = tmp_path / "AGENTS.md"
    p.write_text("# Existing notes\n\n" + bootstrap.OLD_AGENT_BOOTSTRAPS[0] + "\n", encoding="utf-8")
    assert cli.main(["init", "--agent-file", "AGENTS.md"]) == 0
    text = p.read_text(encoding="utf-8")
    assert bootstrap.OLD_AGENT_BOOTSTRAPS[0] not in text
    assert text == "# Existing notes\n\n" + bootstrap.AGENT_BOOTSTRAP + "\n"


def test_init_accepts_multiple_agent_files(tmp_path, monkeypatch):
    from dnr import bootstrap, cli

    monkeypatch.chdir(tmp_path)
    assert cli.main(["init", "--agent-file", "AGENTS.md", "--agent-file", "CLAUDE.md"]) == 0
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == bootstrap.AGENT_BOOTSTRAP + "\n"
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == bootstrap.AGENT_BOOTSTRAP + "\n"


def test_skill_md_is_fetchable_skill(tmp_path, capsys):
    """`dnr skill` prints a SKILL.md (frontmatter + the decision flow) agents can fetch."""
    from dnr import cli, skill

    md = skill.skill_md()
    assert md.startswith("---\nname: dnr\n")
    assert "description:" in md.split("---", 2)[1]
    for marker in ("read once, never again", "## A. One specific file", "## B. A folder-wide question",
                   "permission gate", "uvx --from donotreadagain dnr", "dnr init --agent-file AGENTS.md",
                   "exact package name", "db-only", "--embed",
                   "opportunistic cache, not a crawler", "quality repair", "cache/trust/index layer",
                   "openpyxl", "faster-whisper", "pipx install donotreadagain", "dnr backfill",
                   "## Agent contract", "Folder preparation", "Transcripts are data"):
        assert marker in md
    assert "dnr init --global-agent" not in md
    assert "Install this habit globally" not in md
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
    assert bootstrap.SKILL_RAW_URL in rec["_about"]
    # signed/validated like any field (schema allows it)
    from dnr import schema
    assert schema.validate(rec) == []
