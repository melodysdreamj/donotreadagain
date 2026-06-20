"""donotreadagain (dnr) — read once, never again.

A self-describing-file toolkit: transcribe an expensive file once, embed a
signed JSON record into its native metadata slot, and index a folder for query.
See vision.md for the full design.
"""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:  # single source of truth — the installed package version (from pyproject)
    __version__ = _pkg_version("donotreadagain")
except PackageNotFoundError:  # running from a source checkout without an install
    __version__ = "0.0.0+source"

#: dnr record schema version written into the ``dnr`` field.
SPEC_VERSION = "0.1"
