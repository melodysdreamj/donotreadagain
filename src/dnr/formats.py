"""Supported file types -> transcription method + record storage (M2 / M4).

`storage`: where the record lives — **in-file** (a native metadata slot; portable, travels with
the file) or **db-only** (in the folder's `.dnr.db`; for types with no in-file carrier, or via
`--no-embed`). There are **no sidecar files**.
`status`: implemented | partial | planned.  Value tuple = (modality, method, storage, status).
"""
from __future__ import annotations

SUPPORTED: dict[str, tuple[str, str, str, str]] = {
    # --- documents (visual / layout) ---
    ".pdf":  ("document",    "text-extract (PyMuPDF→pypdf) / vision (scan)", "XMP (in-file)", "partial"),
    ".docx": ("document",    "text-extract (python-docx, local)",         "db-only",         "implemented"),
    ".pptx": ("document",    "text-extract + vision",                     "db-only",         "planned"),
    ".xlsx": ("spreadsheet", "table-extract (openpyxl, local)",           "db-only",         "implemented"),
    ".html": ("document",    "text-extract",                              "db-only",         "planned"),
    ".rtf":  ("document",    "text-extract",                              "db-only",         "planned"),
    ".epub": ("document",    "text-extract",                              "db-only",         "planned"),
    # --- images (record embedded in-file; pixels untouched, content_hash invariant) ---
    ".jpg":  ("image",       "vision (agent, via `dnr record`)",          "JPEG APP (in-file)", "implemented"),
    ".jpeg": ("image",       "vision (agent, via `dnr record`)",          "JPEG APP (in-file)", "implemented"),
    ".png":  ("image",       "vision (agent, via `dnr record`)",          "PNG iTXt (in-file)", "implemented"),
    ".tiff": ("image",       "vision (agent, via `dnr record`)",          "db-only",         "partial"),
    ".webp": ("image",       "vision (agent, via `dnr record`)",          "db-only",         "partial"),
    ".heic": ("image",       "vision (agent, via `dnr record`)",          "db-only",         "planned"),
    # --- audio ---
    ".mp3":  ("audio",       "asr (Whisper, local)",                      "ID3 TXXX (in-file)", "partial"),
    ".wav":  ("audio",       "asr (Whisper, local)",                      "db-only",         "partial"),
    ".flac": ("audio",       "asr (Whisper, local)",                      "db-only",         "planned"),
    ".ogg":  ("audio",       "asr (Whisper, local)",                      "db-only",         "planned"),
    ".opus": ("audio",       "asr (Whisper, local)",                      "db-only",         "planned"),
    ".m4a":  ("audio",       "asr (Whisper, local, audio extra)",         "db-only",         "partial"),
    # --- video ---
    ".mp4":  ("video",       "asr (audio) + vision (keyframes)",          "db-only",         "planned"),
    ".mov":  ("video",       "asr (audio) + vision (keyframes)",          "db-only",         "planned"),
    ".mkv":  ("video",       "asr (audio) + vision (keyframes)",          "db-only",         "planned"),
    ".webm": ("video",       "asr (audio) + vision (keyframes)",          "db-only",         "planned"),
    # --- already-readable text: no transcription, no record (an agent reads it directly) ---
    ".txt":  ("text",        "none (no transcription needed)",            "none (read directly)", "n/a"),
    ".md":   ("text",        "none (no transcription needed)",            "none (read directly)", "n/a"),
    ".json": ("text",        "none (no transcription needed)",            "none (read directly)", "n/a"),
    ".csv":  ("text",        "none (large -> summary+schema: planned)",   "none (read directly)", "n/a"),
    ".tsv":  ("text",        "none (large -> summary+schema: planned)",   "none (read directly)", "n/a"),
    ".log":  ("text",        "none (large -> summary+schema: planned)",   "none (read directly)", "n/a"),
}


def render() -> str:
    head = f"{'ext':7} {'modality':11} {'method':42} {'storage':20} status"
    lines = [head, "-" * len(head)]
    for ext, (mod, method, storage, status) in SUPPORTED.items():
        lines.append(f"{ext:7} {mod:11} {method:42} {storage:20} {status}")
    return "\n".join(lines)
