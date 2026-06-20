"""Local key store (M3) — your own default Ed25519 keypair for signing records.

Lives under ``$DNR_HOME`` (default ``~/.dnr``). The private key is written 0600.
A single user trusts their own public key, so records they made verify and records
forged by others do not (vision.md §9).
"""
from __future__ import annotations

import os
from pathlib import Path

from . import signing


def home() -> Path:
    base = os.environ.get("DNR_HOME") or (Path.home() / ".dnr")
    return Path(base)


def _key_dir() -> Path:
    d = home() / "keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_keypair() -> tuple[bytes, bytes]:
    """Load the local default keypair, creating it on first use. Returns ``(priv, pub)``."""
    d = _key_dir()
    priv_p, pub_p = d / "default.ed25519", d / "default.ed25519.pub"
    if priv_p.exists() and pub_p.exists():
        return priv_p.read_bytes(), pub_p.read_bytes()
    priv, pub = signing.generate_keypair()
    fd = os.open(priv_p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, priv)
    finally:
        os.close(fd)
    pub_p.write_bytes(pub)
    return priv, pub


def default_trust() -> dict[str, bytes]:
    """Trust list containing just your own public key."""
    _, pub = default_keypair()
    return {signing.key_id(pub): pub}
