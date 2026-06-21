"""Minimal dnr read-through cache adapter for Python agent harnesses.

Copy the shape, not necessarily this exact file. The important behavior:
dnr misses are soft, normal parsing still happens, and cache writes never fail
the user task.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import shutil
import subprocess
import tempfile


Parser = Callable[[Path], str]


def _dnr_bin() -> str | None:
    return shutil.which("dnr")


def _run(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    dnr = _dnr_bin()
    if not dnr:
        return None
    try:
        return subprocess.run(
            [dnr, *args],
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        return None


def read_cached_transcript(path: str | Path) -> str | None:
    """Return a verified cached transcript, or None on any miss."""
    result = _run(["read", str(Path(path))])
    if result is None or result.returncode != 0:
        return None
    transcript = result.stdout
    return transcript if transcript.strip() else None


def cache_transcript(
    path: str | Path,
    transcript: str,
    *,
    method: str,
    transcriber: str,
) -> None:
    """Best-effort cache write. Never raise into the user task."""
    if not transcript.strip():
        return
    transcript_file: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as tmp:
            tmp.write(transcript)
            transcript_file = Path(tmp.name)
        _run(
            [
                "record",
                str(Path(path)),
                "--transcript-file",
                str(transcript_file),
                "--method",
                method,
                "--transcriber",
                transcriber,
            ]
        )
    except OSError:
        return
    finally:
        if transcript_file is not None:
            try:
                transcript_file.unlink(missing_ok=True)
            except OSError:
                pass


def read_with_dnr_cache(
    path: str | Path,
    normal_reader: Parser,
    *,
    method: str,
    transcriber: str,
) -> str:
    """Use dnr if present; otherwise fall back to the harness's normal reader."""
    p = Path(path)
    cached = read_cached_transcript(p)
    if cached is not None:
        return cached

    transcript = normal_reader(p)
    cache_transcript(p, transcript, method=method, transcriber=transcriber)
    return transcript


def query_folder(folder: str | Path, *query_args: str) -> str | None:
    """Index, then query cached folder transcripts. Returns stdout or None on soft miss."""
    _run(["index", str(Path(folder))])
    result = _run(["query", str(Path(folder)), *query_args])
    if result is None or result.returncode != 0:
        return None
    return result.stdout
