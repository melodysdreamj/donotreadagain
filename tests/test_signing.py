from dnr import signing


def _trust(pub):
    return {signing.key_id(pub): pub}


def test_sign_verify_roundtrip(sample_record):
    priv, pub = signing.generate_keypair()
    signed = signing.sign(sample_record, priv, pub)
    assert signed["sig"]["alg"] == "ed25519"
    assert signing.verify(signed, _trust(pub)) is True


def test_untrusted_key_rejected(sample_record):
    priv, pub = signing.generate_keypair()
    signed = signing.sign(sample_record, priv, pub)
    _, other_pub = signing.generate_keypair()
    assert signing.verify(signed, _trust(other_pub)) is False


def test_tamper_rejected(sample_record):
    priv, pub = signing.generate_keypair()
    signed = signing.sign(sample_record, priv, pub)
    signed["fields"]["title"] = "TAMPERED"
    assert signing.verify(signed, _trust(pub)) is False


def test_unsigned_rejected(sample_record):
    _, pub = signing.generate_keypair()
    assert signing.verify(sample_record, _trust(pub)) is False
