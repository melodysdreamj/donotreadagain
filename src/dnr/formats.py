"""Supported file types -> transcription method + record storage (M2 / M4).

`storage`: where the record lives by default. dnr stores records **db-only** in the folder's
`.dnr.db` so originals stay byte-identical. Some formats also support opt-in in-file carriers via
`--embed`. There are **no sidecar files**.
`status`: implemented | partial | planned.  Value tuple = (modality, method, storage, status).
"""
from __future__ import annotations

SUPPORTED: dict[str, tuple[str, str, str, str]] = {
    # --- documents (visual / layout) ---
    ".pdf":  ("document",    "text-extract (PyMuPDF→pypdf) / vision (scan)", "db-only; --embed XMP", "partial"),
    ".docx": ("document",    "text-extract (python-docx, local)",         "db-only",         "implemented"),
    ".pptx": ("document",    "text-extract + vision",                     "db-only",         "planned"),
    ".xlsx": ("spreadsheet", "table-extract (openpyxl, local)",           "db-only",         "implemented"),
    ".html": ("document",    "text-extract",                              "db-only",         "planned"),
    ".rtf":  ("document",    "text-extract",                              "db-only",         "planned"),
    ".epub": ("document",    "text-extract",                              "db-only",         "planned"),
    # --- images (db-only by default; --embed can write metadata without touching pixels) ---
    ".jpg":  ("image",       "vision (agent, via `dnr record`)",          "db-only; --embed JPEG APP", "implemented"),
    ".jpeg": ("image",       "vision (agent, via `dnr record`)",          "db-only; --embed JPEG APP", "implemented"),
    ".png":  ("image",       "vision (agent, via `dnr record`)",          "db-only; --embed PNG iTXt", "implemented"),
    ".tiff": ("image",       "vision (agent, via `dnr record`)",          "db-only",         "partial"),
    ".webp": ("image",       "vision (agent, via `dnr record`)",          "db-only",         "partial"),
    ".heic": ("image",       "vision (agent; optional pillow-heif hash)", "db-only",         "partial"),
    ".heif": ("image",       "vision (agent; optional pillow-heif hash)", "db-only",         "partial"),
    # --- audio ---
    ".mp3":  ("audio",       "asr (Whisper, local)",                      "db-only; --embed ID3", "partial"),
    ".wav":  ("audio",       "asr (Whisper, local)",                      "db-only",         "partial"),
    ".flac": ("audio",       "asr (Whisper, local)",                      "db-only; --embed Vorbis", "partial"),
    ".ogg":  ("audio",       "asr (Whisper, local)",                      "db-only; --embed Vorbis", "partial"),
    ".opus": ("audio",       "asr (Whisper, local)",                      "db-only; --embed Opus", "partial"),
    ".m4a":  ("audio",       "asr (Whisper, local, audio extra)",         "db-only; --embed MP4 atom", "partial"),
    # --- video ---
    ".mp4":  ("video",       "agent transcript / ASR + vision",           "db-only; --embed MP4 atom", "partial"),
    ".mov":  ("video",       "agent transcript / ASR + vision",           "db-only; --embed MP4 atom", "partial"),
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
