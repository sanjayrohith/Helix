"""ETag generation for optimistic concurrency on mutable resources.

PATCH /api/slices/{id} had no way to detect a lost update: two operators
reading the same slice, both computing a change from what they saw, and
both PATCHing - the second write silently overwrites the first with no
signal that anything was lost. Standard HTTP conditional requests
(`ETag` / `If-Match`) fix this without inventing a bespoke versioning
scheme: a GET returns an ETag identifying the exact state read, and a PATCH
that supplies `If-Match` with a now-stale ETag is rejected with 412 instead
of silently succeeding over lost work.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel


def compute_etag(model: BaseModel) -> str:
    """A weak-comparison-safe ETag for the current state of ``model``.

    Content-derived (a hash of the serialised model) rather than a separate
    incrementing version counter: it needs no extra column, and it is
    automatically correct for the fields already being compared - two reads
    of identical content always agree, without HELIX having to remember to
    bump a counter on every field it might someday add.
    """
    digest = hashlib.sha256(model.model_dump_json().encode()).hexdigest()[:32]
    return f'"{digest}"'


def matches(etag: str, if_match_header: str) -> bool:
    """Compare an ETag against a (possibly multi-valued) If-Match header.

    Handles the wildcard '*' (matches any current representation) and a
    comma-separated list of ETags, per RFC 7232 - a client is allowed to
    send several ETags it considers acceptable preconditions.
    """
    header = if_match_header.strip()
    if header == "*":
        return True
    candidates = [candidate.strip() for candidate in header.split(",")]
    return etag in candidates
