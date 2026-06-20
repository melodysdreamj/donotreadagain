"""The verbatim transcription guide (M4).

dnr ships no model — it ships this GUIDE. A transcriber (usually the calling agent
for visual docs) follows it to produce a faithful, complete transcript. The record's
provenance stamps the guide's id + hash, so "this transcript followed the official
verbatim contract" is auditable (vision.md §8).
"""
from __future__ import annotations

import hashlib

INSTRUCTION_ID = "dnr-verbatim-1"

GUIDE = """\
Transcribe this file VERBATIM and COMPLETE. You are producing a faithful copy, not a summary.

Rules:
- Output the ENTIRE content, in original order. Do not truncate, omit, or write "..." / "rest omitted".
- Do NOT summarize, paraphrase, translate, "fix", or add commentary. Reproduce exactly what is there.
- Preserve structure: headings, lists, tables (as markdown tables), page breaks, speaker labels, timestamps.
- Mark anything illegible or uncertain explicitly: [illegible] or [unclear: best-guess]. Never invent text.
- Preserve the original language. If you must translate, keep the original and clearly mark the translation.
- Audio/video: transcribe all speech verbatim with timestamps; label speakers when distinguishable.
- Images/scans: transcribe all visible text exactly, then note non-text visual content briefly and factually.

Output only the transcript (markdown). No preamble, no "Here is the transcript".
"""


def prompt_hash() -> str:
    """Stable hash of the guide text — bound into provenance."""
    return "sha256:" + hashlib.sha256(GUIDE.encode("utf-8")).hexdigest()


def provenance_stamp(method: str, transcriber: str, **extra) -> dict:
    """Provenance for a transcript produced by following this guide."""
    p = {
        "method": method,
        "transcriber": transcriber,
        "instruction_id": INSTRUCTION_ID,
        "prompt_hash": prompt_hash(),
    }
    p.update({k: v for k, v in extra.items() if v is not None})
    return p
