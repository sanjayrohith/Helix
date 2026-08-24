"""Offset/limit pagination that never changes a response's JSON shape.

GET /api/slices and GET /api/events returned every matching row, unbounded -
fine at demo scale, a real liability once an instance has been running for
months. The obvious fix is a paginated envelope
(`{"items": [...], "total": N}`), but that is a breaking change: every
existing caller, including this project's own frontend and test suite,
expects a bare array back.

The fix used here is the same one GitHub's REST API uses: keep the response
body a plain array, and carry pagination metadata in `X-Total-Count` and an
RFC 5988 `Link` header (`rel="next"`, `rel="prev"`). A client that ignores
the headers still works exactly as before, just capped to a page; a client
that wants to page through everything reads the `Link` header the way it
already knows how to for GitHub, Stripe, or any other API following the same
convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from fastapi import Request, Response

# A single request that omits limit/offset gets this many rows - enough for
# any reasonable dashboard view without being an accidental "return everything".
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


@dataclass(frozen=True)
class Page:
    """One slice of a larger result set."""

    offset: int
    limit: int
    total: int

    @property
    def has_next(self) -> bool:
        return self.offset + self.limit < self.total

    @property
    def has_prev(self) -> bool:
        return self.offset > 0


def paginate(items: list, offset: int, limit: int) -> Page:
    """Return pagination metadata for slicing ``items[offset:offset+limit]``."""
    return Page(offset=offset, limit=limit, total=len(items))


def apply_pagination_headers(response: Response, request: Request, page: Page) -> None:
    """Set X-Total-Count and Link on ``response`` for the given page."""
    response.headers["X-Total-Count"] = str(page.total)

    links: list[str] = []
    base = str(request.url.remove_query_params(["offset", "limit"]))
    separator = "&" if "?" in base else "?"

    def link(offset: int, rel: str) -> str:
        query = urlencode({"offset": offset, "limit": page.limit})
        return f'<{base}{separator}{query}>; rel="{rel}"'

    if page.has_next:
        links.append(link(page.offset + page.limit, "next"))
    if page.has_prev:
        links.append(link(max(0, page.offset - page.limit), "prev"))
    links.append(link(0, "first"))
    if page.total > 0:
        last_offset = ((page.total - 1) // page.limit) * page.limit
        links.append(link(last_offset, "last"))

    if links:
        response.headers["Link"] = ", ".join(links)
