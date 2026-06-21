"""Signing & trust (M3).

A cached record is untrusted by default. ``skip-reparse`` is unlocked only when
the record is signed by a trusted key AND its content_hash matches the file
(vision.md §9). Ed25519: 64-byte signatures, 32-byte public keys.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from . import record as _record


def generate_keypair() -> tuple[bytes, bytes]:
    """Return ``(private_raw, public_raw)`` — 32 bytes each."""
    priv = Ed25519PrivateKey.generate()
    priv_raw = priv.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    pub_raw = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return priv_raw, pub_raw


def key_id(pub_raw: bytes) -> str:
    """Short, stable identifier for a public key."""
    return hashlib.sha256(pub_raw).hexdigest()[:16]


def sign(record: dict, priv_raw: bytes, pub_raw: bytes) -> dict:
    """Return ``record`` with a ``sig`` field over JCS(record − sig)."""
    priv = Ed25519PrivateKey.from_private_bytes(priv_raw)
    signature = priv.sign(_record.canonicalize(record))
    signed = {k: v for k, v in record.items() if k != "sig"}
    signed["sig"] = {
        "alg": "ed25519",
        "key_id": key_id(pub_raw),
        "value": base64.b64encode(signature).decode("ascii"),
    }
    return signed


def verify(record: dict, trust_list: dict[str, bytes]) -> bool:
    """True iff the record is signed by a key in ``trust_list`` and the sig is valid.

    ``trust_list`` maps ``key_id -> public_raw``. Tampering (any field change after
    signing) invalidates the signature.
    """
    sig = record.get("sig")
    if not isinstance(sig, dict) or sig.get("alg") != "ed25519":
        return False
    pub_raw = trust_list.get(sig.get("key_id"))
    if pub_raw is None:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(pub_raw).verify(
            base64.b64decode(sig["value"]), _record.canonicalize(record)
        )
        return True
    except Exception:
        return False
