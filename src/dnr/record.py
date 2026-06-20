"""The dnr record — build + canonical serialization (M1).

The record is signed/hashed over its **RFC 8785 (JCS) canonical form excluding the
``sig`` field**, so two implementations agree byte-for-byte (vision.md §6, §9).
"""
from __future__ import annotations

import hashlib

import rfc8785

from . import SPEC_VERSION, bootstrap


def canonicalize(record: dict) -> bytes:
    """RFC 8785 JCS canonical bytes of the record WITHOUT its ``sig`` field."""
    body = {k: v for k, v in record.items() if k != "sig"}
    out = rfc8785.dumps(body)
    return out if isinstance(out, (bytes, bytearray)) else out.encode("utf-8")


def record_hash(record: dict) -> str:
    """sha256 of the canonical record (excluding ``sig``)."""
    return "sha256:" + hashlib.sha256(canonicalize(record)).hexdigest()


def new_record(*, content_hash: str, source: dict, transcript: dict | None = None,
               provenance: dict | None = None, fields: dict | None = None,
               extras: dict | None = None) -> dict:
    """Assemble a v0.1 record dict (unsigned). Sign with :mod:`dnr.signing`."""
    rec: dict = {
        "dnr": SPEC_VERSION,
        "_about": bootstrap.ABOUT,  # one-line self-introduction so the file advertises itself
        "content_hash": content_hash,
        "source": source,
    }
    if transcript is not None:
        rec["transcript"] = transcript
    rec["provenance"] = provenance or {}
    rec["fields"] = fields or {}
    rec["extras"] = extras or {}
    return rec
