"""Supported file types -> transcription method + record carrier (M2 / M4).

`status`: implemented | partial | planned.  Value tuple = (modality, method, carrier, status).
"""
from __future__ import annotations

SUPPORTED: dict[str, tuple[str, str, str, str]] = {
    # --- documents (visual / layout) ---
    ".pdf":  ("document",    "text-extract (text layer) / vision (scan)", "XMP",         "partial"),
    ".docx": ("document",    "text-extract (python-docx, local)",         "sidecar",     "implemented"),
    ".pptx": ("document",    "text-extract + vision",                     "OOXML part",  "planned"),
    ".xlsx": ("spreadsheet", "table-extract -> summary+schema",           "OOXML part",  "planned"),
    ".html": ("document",    "text-extract",                              "sidecar",     "planned"),
    ".rtf":  ("document",    "text-extract",                              "sidecar",     "planned"),
    ".epub": ("document",    "text-extract",                              "sidecar",     "planned"),
    # --- images ---
    ".jpg":  ("image",       "vision (agent, via `dnr record`)",          "sidecar",     "implemented"),
    ".jpeg": ("image",       "vision (agent, via `dnr record`)",          "sidecar",     "implemented"),
    ".png":  ("image",       "vision (agent, via `dnr record`)",          "sidecar",     "implemented"),
    ".tiff": ("image",       "vision (agent, via `dnr record`)",          "sidecar",     "implemented"),
    ".webp": ("image",       "vision (agent, via `dnr record`)",          "sidecar",     "implemented"),
    ".heic": ("image",       "vision (agent, via `dnr record`)",          "sidecar",     "planned"),
    # --- audio ---
    ".mp3":  ("audio",       "asr (Whisper, local)",                      "ID3 TXXX",    "partial"),
    ".wav":  ("audio",       "asr (Whisper, local)",                      "sidecar",     "partial"),
    ".flac": ("audio",       "asr (Whisper, local)",                      "Vorbis",      "planned"),
    ".ogg":  ("audio",       "asr (Whisper, local)",                      "Vorbis",      "planned"),
    ".opus": ("audio",       "asr (Whisper, local)",                      "Vorbis",      "planned"),
    ".m4a":  ("audio",       "asr (Whisper, local)",                      "MP4 atom",    "planned"),
    # --- video ---
    ".mp4":  ("video",       "asr (audio) + vision (keyframes)",          "XMP",         "planned"),
    ".mov":  ("video",       "asr (audio) + vision (keyframes)",          "XMP",         "planned"),
    ".mkv":  ("video",       "asr (audio) + vision (keyframes)",          "sidecar",     "planned"),
    ".webm": ("video",       "asr (audio) + vision (keyframes)",          "sidecar",     "planned"),
    # --- already-text: no transcription (method=none); stored as a sidecar ---
    ".txt":  ("text",        "none (no transcription needed)",            "sidecar",     "implemented"),
    ".md":   ("text",        "none (no transcription needed)",            "sidecar",     "implemented"),
    ".json": ("text",        "none (no transcription needed)",            "sidecar",     "implemented"),
    ".csv":  ("text",        "none (large -> summary+schema: planned)",   "sidecar",     "implemented"),
    ".tsv":  ("text",        "none (large -> summary+schema: planned)",   "sidecar",     "implemented"),
    ".log":  ("text",        "none (large -> summary+schema: planned)",   "sidecar",     "implemented"),
}


def render() -> str:
    head = f"{'ext':7} {'modality':11} {'method':42} {'carrier':18} status"
    lines = [head, "-" * len(head)]
    for ext, (mod, method, carrier, status) in SUPPORTED.items():
        lines.append(f"{ext:7} {mod:11} {method:42} {carrier:18} {status}")
    return "\n".join(lines)
