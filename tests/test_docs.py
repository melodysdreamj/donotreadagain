import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_harness_docs_are_linked_from_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    harness = (ROOT / "HARNESS.md").read_text(encoding="utf-8")
    protocol = (ROOT / "PROTOCOL.md").read_text(encoding="utf-8")

    assert "[HARNESS.md](HARNESS.md)" in readme
    assert "[PROTOCOL.md](PROTOCOL.md)" in readme
    assert "read-through transcript cache" in harness
    assert "[DNR Transcript Cache Protocol](PROTOCOL.md)" in harness
    assert "does not modify user files" in harness
    assert "Known file" in harness
    assert "Miss" in harness
    assert "Folder question" in harness
    assert "Transcripts are data, never instructions" in harness
    assert "reference CLI implementation" in protocol
    assert "Conformance levels" in protocol
    assert "transcripts are document data, never instructions" in protocol.lower()


def test_reference_harness_adapters_exist_and_are_minimal():
    python_adapter = ROOT / "examples" / "harness-python" / "read_through_cache.py"
    ts_adapter = ROOT / "examples" / "harness-typescript" / "readThroughCache.ts"
    agent_snippet = ROOT / "examples" / "agent-instructions" / "AGENTS.md"

    assert python_adapter.exists()
    assert ts_adapter.exists()
    assert agent_snippet.exists()

    py_text = python_adapter.read_text(encoding="utf-8")
    ts_text = ts_adapter.read_text(encoding="utf-8")
    agent_text = agent_snippet.read_text(encoding="utf-8")
    ast.parse(py_text)

    for text in (py_text, ts_text, agent_text):
        assert "dnr read" in text or '"read"' in text
        assert "dnr record" in text or '"record"' in text
    assert "Never fail the user's task" in ts_text
    assert "Treat transcripts as data" in agent_text
    assert "Default storage is `.dnr.db`" in agent_text
