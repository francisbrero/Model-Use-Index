"""Capture. This layer does no interpretation (invariant 2, TD §2.1).

It extracts only enough to find a session id and a content hash, appends the
verbatim payload to `raw_event`, and moves on. It therefore CANNOT be broken by
a transcript schema change, because it does not understand the schema. All
parsing lives in `normalize/`, where a failure is recoverable by fixing the
parser and re-running over `raw_event`.

Never add parsing, validation or field extraction here. A Pydantic model in
this package is the specific mistake the invariant exists to prevent — it turns
a structural guarantee back into an aspiration.
"""
