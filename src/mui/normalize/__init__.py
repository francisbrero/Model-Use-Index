"""Derivation. Everything that understands the transcript schema lives here.

This is the other half of invariant 2: `collect/` cannot be broken by a schema
change because it does not parse, and a parse failure here is recoverable by
fixing the parser and re-running over `raw_event` (invariant 2b). The directory
split IS that boundary made physical (TD §12) — keep it visible.
"""
