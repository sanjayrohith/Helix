"""Audit journal: an append-only record of what happened to the network.

Every provisioning attempt, conflict, lifecycle change and SLA transition
lands here. The journal is kept both in memory (fast reads for the dashboard)
and in SQLite (survives a restart), and it is what makes a HELIX deployment
explainable after the fact.
"""

from __future__ import annotations

import uuid
from collections import deque
from threading import RLock

from core.logging_config import get_logger
from models.event_models import AuditEvent, EventSeverity, EventType
from models.slice_models import SliceConfig
from storage.sqlite_store import get_store

logger = get_logger("audit")

IN_MEMORY_CAPACITY = 500

# Offset-based paging fetches offset+limit rows and slices in Python rather
# than pushing OFFSET down to SQLite, since the in-memory tail and the disk
# fallback would otherwise need two different pagination implementations.
# Capped here to match the journal's own default retention (prune_events
# keeps 5000 by default), so a caller cannot page arbitrarily deep into
# history that may not even be retained.
MAX_QUERY_WINDOW = 5000


class AuditLog:
    """Append-only event journal with a bounded in-memory tail."""

    def __init__(self, capacity: int = IN_MEMORY_CAPACITY) -> None:
        self._events: deque[AuditEvent] = deque(maxlen=capacity)
        self._lock = RLock()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Warm the in-memory tail from the durable journal on first read."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            for event in reversed(get_store().load_events(limit=self._events.maxlen or 500)):
                self._events.append(event)
            self._loaded = True

    def record(
        self,
        event_type: EventType,
        summary: str,
        *,
        severity: EventSeverity = "info",
        slice_id: str | None = None,
        slice_name: str | None = None,
        actor: str = "system",
        detail: dict | None = None,
    ) -> AuditEvent:
        """Append an event to the journal and return it."""
        self._ensure_loaded()
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            slice_id=slice_id,
            slice_name=slice_name,
            actor=actor,
            summary=summary,
            detail=detail or {},
        )
        with self._lock:
            self._events.append(event)
        get_store().append_event(event)

        log = logger.warning if severity == "warning" else (
            logger.error if severity == "error" else logger.info
        )
        log("[audit] %s: %s", event_type, summary)
        return event

    def record_slice_event(
        self,
        event_type: EventType,
        config: SliceConfig,
        summary: str,
        *,
        severity: EventSeverity = "info",
        actor: str = "system",
        detail: dict | None = None,
    ) -> AuditEvent:
        """Convenience wrapper that fills identity fields from a slice."""
        payload = {"snssai": config.snssai, "use_case": config.use_case, **(detail or {})}
        return self.record(
            event_type,
            summary,
            severity=severity,
            slice_id=config.slice_id,
            slice_name=config.name,
            actor=actor,
            detail=payload,
        )

    def query(
        self,
        limit: int = 100,
        offset: int = 0,
        slice_id: str | None = None,
        # str rather than the EventType/EventSeverity Literal: this is the
        # HTTP query-param boundary's filter, and an unrecognised value
        # should behave as "matches nothing" (correct filter behaviour), not
        # a type error - matching the same choice already made for
        # SqliteStore.load_events, which this falls through to.
        event_type: str | None = None,
        severity: str | None = None,
    ) -> list[AuditEvent]:
        """Return matching events newest-first, `offset` rows into the result."""
        window = min(offset + limit, MAX_QUERY_WINDOW)

        self._ensure_loaded()
        with self._lock:
            events = list(self._events)

        if slice_id:
            events = [e for e in events if e.slice_id == slice_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if severity:
            events = [e for e in events if e.severity == severity]

        events.reverse()  # newest first
        if len(events) < window and get_store().enabled:
            # The in-memory tail may not reach far enough back; fall through to disk.
            events = get_store().load_events(
                limit=window, slice_id=slice_id, event_type=event_type, severity=severity
            ) or events
        else:
            events = events[:window]

        return events[offset : offset + limit]

    def count(
        self,
        slice_id: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
    ) -> int:
        """Total matching events, for pagination headers.

        Bounded by MAX_QUERY_WINDOW for the same reason `query` is: this is
        a count of what is realistically retained and pageable, not a
        promise that every event ever recorded is reachable.
        """
        return len(
            self.query(limit=MAX_QUERY_WINDOW, slice_id=slice_id, event_type=event_type, severity=severity)
        )

    def summary(self) -> dict:
        """Counts by severity and type, for the dashboard's activity panel."""
        self._ensure_loaded()
        with self._lock:
            events = list(self._events)
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for event in events:
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
            by_severity[event.severity] = by_severity.get(event.severity, 0) + 1
        return {
            "total_retained": len(events),
            "by_type": by_type,
            "by_severity": by_severity,
        }

    def clear(self) -> None:
        """Drop the in-memory tail. The durable journal is untouched."""
        with self._lock:
            self._events.clear()
            self._loaded = False


audit_log = AuditLog()
