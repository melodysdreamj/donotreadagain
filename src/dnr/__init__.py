"""donotreadagain (dnr) — read once, never again.

A self-describing-file toolkit: transcribe an expensive file once, embed a
signed JSON record into its native metadata slot, and index a folder for query.
See vision.md for the full design.
"""

__version__ = "0.1.0.dev0"

#: dnr record schema version written into the ``dnr`` field.
SPEC_VERSION = "0.1"
