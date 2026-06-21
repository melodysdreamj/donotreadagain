"""The dnr record JSON Schema (M12) + a validator.

This is the machine-checkable contract for a record (the prose spec lives in
`spec/dnr-0.1.md`). `spec/dnr.schema.json` is the published copy of `SCHEMA`.
"""
from __future__ import annotations

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ns.donotreadagain.org/dnr-0.1.schema.json",
    "title": "dnr record",
    "type": "object",
    "required": ["dnr", "content_hash", "source"],
    "properties": {
        "dnr": {"type": "string", "const": "0.1"},
        "_about": {"type": "string", "description": "informational pointer to the skill/spec"},
        "content_hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
        "source": {
            "type": "object",
            "required": ["mime"],
            "properties": {
                "mime": {"type": "string"},
                "bytes": {"type": "integer", "minimum": 0},
                "pages": {"type": "integer", "minimum": 0},
            },
        },
        "transcript": {
            "type": "object",
            "properties": {
                "format": {"type": "string"},
                "lang": {"type": ["string", "null"]},
                "text": {"type": "string"},
                "segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"t": {"type": "number"}, "text": {"type": "string"}},
                    },
                },
            },
        },
        "provenance": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["text-extract", "vision", "ocr", "asr", "none"]},
                "transcriber": {"type": "string"},
                "version": {"type": ["string", "null"]},
                "instruction_id": {"type": "string"},
                "prompt_hash": {"type": "string"},
                "params_hash": {"type": "string"},
                "confidence": {"type": "number"},
                "created_at": {"type": "string"},
            },
        },
        "fields": {"type": "object"},
        "extras": {"type": "object"},
        "sig": {
            "type": "object",
            "required": ["alg", "key_id", "value"],
            "properties": {
                "alg": {"type": "string"},
                "key_id": {"type": "string"},
                "value": {"type": "string"},
            },
        },
    },
    "additionalProperties": True,
}


def validate(record: dict) -> list[str]:
    """Return a list of human-readable validation errors ([] = valid)."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed (pip install jsonschema)"]
    validator = jsonschema.Draft202012Validator(SCHEMA)
    errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
