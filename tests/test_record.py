from dnr import record


def test_canonical_is_key_order_independent():
    a = {"b": 1, "a": 2, "dnr": "0.1"}
    b = {"dnr": "0.1", "a": 2, "b": 1}
    assert record.canonicalize(a) == record.canonicalize(b)


def test_canonical_excludes_sig():
    base = {"dnr": "0.1", "content_hash": "sha256:x"}
    with_sig = dict(base, sig={"alg": "ed25519", "value": "zzz"})
    assert record.canonicalize(base) == record.canonicalize(with_sig)


def test_record_hash_stable_and_prefixed():
    r = {"dnr": "0.1", "content_hash": "sha256:x", "fields": {"k": [1, 2]}}
    h = record.record_hash(r)
    assert h.startswith("sha256:")
    assert h == record.record_hash(dict(reversed(list(r.items()))))


def test_new_record_shape():
    r = record.new_record(content_hash="sha256:x", source={"mime": "application/pdf"})
    assert r["dnr"] == "0.1"
    assert r["content_hash"] == "sha256:x"
    assert r["fields"] == {} and r["extras"] == {}
