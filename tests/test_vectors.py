"""Golden conformance vectors (spec/vectors/) — the reference impl must reproduce them,
and so must any independent implementation (M12)."""
import json
from pathlib import Path

VECTORS = Path(__file__).resolve().parent.parent / "spec" / "vectors"


def test_golden_vectors_reproduce():
    from dnr import hashing

    manifest = json.loads((VECTORS / "vectors.json").read_text(encoding="utf-8"))
    assert manifest, "no vectors found"
    for fname, info in manifest.items():
        got = hashing.content_hash(VECTORS / fname)
        assert got == info["content_hash"], f"{fname}: {got} != {info['content_hash']}"
