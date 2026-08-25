"""API-key authentication with read/write scopes.

HELIX had no authentication at all: any request could suspend, delete or
reconfigure any slice. Given the actual shape of this system - an internal
network-operations tool, not a multi-tenant SaaS product - full OAuth2/JWT
with session management would be over-engineering that adds an entire class
of new bugs (password storage, token refresh, session fixation) to guard
against for a threat model that does not need it. API keys with two scopes
is what infrastructure tools at this scope actually use (Grafana, most
internal SRE dashboards), and it maps directly onto the one distinction that
matters here: can this caller only look, or can it change the network.

Auth is opt-in, matching the LLM-parser pattern already used elsewhere in
this codebase: unset HELIX_API_KEYS and every request is treated as an
authenticated "system" principal with full access, so a demo, a local
`make dev`, and the existing test suite all keep working with zero
configuration. Configure at least one key and the API starts enforcing scopes
on every route - there is no way to leave it half-on.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, HTTPException, Request

from core.config import settings
from core.logging_config import get_logger

logger = get_logger("auth")

Scope = Literal["read", "write"]

# A principal that satisfies "write" also satisfies "read": an operator can
# do everything a viewer can.
_SCOPE_RANK: dict[Scope, int] = {"read": 0, "write": 1}

_SYSTEM_PRINCIPAL_LABEL = "system"


@dataclass(frozen=True)
class Principal:
    """The caller identified by a request, however it was authenticated."""

    actor: str
    scope: Scope

    def satisfies(self, required: Scope) -> bool:
        return _SCOPE_RANK[self.scope] >= _SCOPE_RANK[required]


SYSTEM_PRINCIPAL = Principal(actor=_SYSTEM_PRINCIPAL_LABEL, scope="write")


def parse_api_keys(raw: str) -> dict[str, Principal]:
    """Parse HELIX_API_KEYS into a lookup of key -> principal.

    Format: comma-separated `key:scope[:label]` entries, e.g.
    `sk_abc123:write:ops-team,sk_def456:read:dashboard`. A label defaults to
    a redacted form of the key itself so the audit journal never has to
    choose between an unhelpful "system" actor and logging a secret in full.

    Malformed entries are skipped with a warning rather than raising, so one
    typo in the environment does not take the whole API down.
    """
    keys: dict[str, Principal] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue

        parts = entry.split(":")
        if len(parts) not in (2, 3):
            logger.warning("Skipping malformed HELIX_API_KEYS entry (wrong field count)")
            continue

        key, scope_text = parts[0].strip(), parts[1].strip().lower()
        label = parts[2].strip() if len(parts) == 3 and parts[2].strip() else None

        if not key:
            logger.warning("Skipping HELIX_API_KEYS entry with an empty key")
            continue
        if scope_text not in ("read", "write"):
            logger.warning(
                "Skipping API key for '%s': scope must be 'read' or 'write', got '%s'",
                label or redact(key),
                scope_text,
            )
            continue

        keys[key] = Principal(actor=label or redact(key), scope=scope_text)  # type: ignore[arg-type]
    return keys


def redact(key: str) -> str:
    """A stable, non-reversible label for a key, safe to put in logs."""
    digest = hashlib.sha256(key.encode()).hexdigest()[:8]
    return f"key-{digest}"


def _extract_key(request: Request) -> str | None:
    """Read a caller-supplied key from Authorization: Bearer or X-API-Key."""
    header = request.headers.get("Authorization")
    if header:
        scheme, _, token = header.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token.strip()
    return request.headers.get("X-API-Key")


def _authenticate(request: Request) -> Principal:
    """Resolve the calling principal, raising 401 for a missing/unknown key."""
    keys = parse_api_keys(settings.api_keys_raw)
    if not keys:
        # Auth is not configured on this instance: preserve the pre-auth
        # behaviour exactly rather than silently locking everyone out.
        return SYSTEM_PRINCIPAL

    supplied = _extract_key(request)
    if not supplied:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Send it as 'Authorization: Bearer <key>' or 'X-API-Key: <key>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Constant-time comparison against every configured key avoids a timing
    # side-channel that could otherwise help an attacker guess a valid key
    # byte-by-byte.
    for candidate, principal in keys.items():
        if secrets.compare_digest(supplied, candidate):
            return principal

    logger.warning("Rejected request with an unrecognised API key")
    raise HTTPException(
        status_code=401,
        detail="Invalid API key.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_read(request: Request) -> Principal:
    """Dependency: the caller must hold at least the 'read' scope."""
    principal = _authenticate(request)
    if not principal.satisfies("read"):
        raise HTTPException(status_code=403, detail="This key does not grant read access.")
    return principal


def require_write(request: Request) -> Principal:
    """Dependency: the caller must hold the 'write' scope."""
    principal = _authenticate(request)
    if not principal.satisfies("write"):
        raise HTTPException(
            status_code=403,
            detail="This key does not grant write access; a 'write'-scoped key is required.",
        )
    return principal


def try_authenticate_websocket(api_key: str | None) -> Principal | None:
    """Authenticate a WebSocket connection from its `?api_key=` query param.

    WebSocket clients in a browser cannot set custom headers on the opening
    handshake, so a query parameter is the practical option despite the
    downside that it can end up in access logs - acceptable here because the
    key only grants read access to already-public telemetry, never a write
    scope. Returns None (rather than raising) so the caller can close the
    connection with a WebSocket-appropriate code instead of an HTTP one.
    """
    keys = parse_api_keys(settings.api_keys_raw)
    if not keys:
        return SYSTEM_PRINCIPAL
    if not api_key:
        return None
    for candidate, principal in keys.items():
        if secrets.compare_digest(api_key, candidate):
            return principal
    return None


# Convenience aliases for use in route signatures: `principal: Principal =
# Depends(ReadScope)` reads slightly cleaner than repeating Depends(require_read).
ReadScope = Depends(require_read)
WriteScope = Depends(require_write)
