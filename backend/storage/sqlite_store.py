"""SQLite-backed persistence for slices and audit events.

The registry was purely in-memory, so restarting the API lost every slice an
operator had provisioned. This store keeps a durable copy without adding an
ORM dependency: the schema is small, stable and written by hand.

Writes are synchronous and wrapped in a lock. At HELIX's scale (hundreds of
slices, a handful of writes per minute) that is far cheaper than the
complexity of an async driver, and it keeps the registry API unchanged.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from core.config import settings
from core.logging_config import get_logger
from models.event_models import AuditEvent
from models.slice_models import SliceConfig
from storage.migrations import LATEST_VERSION, current_version, run_migrations

logger = get_logger("storage")


class SqliteStore:
    """Durable storage for slice configurations and audit events."""

    def __init__(self, path: Path | str | None = None, enabled: bool | None = None) -> None:
        self.enabled = settings.persistence_enabled if enabled is None else enabled
        self.path = Path(path) if path else settings.database_path
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        if self.enabled:
            self._connect()

    # --- connection management ------------------------------------------------

    def _connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL keeps reads from blocking the telemetry writer.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            version = run_migrations(self._conn)
        logger.info("SQLite store ready at %s (schema version %d)", self.path, version)

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @property
    def _db(self) -> sqlite3.Connection | None:
        return self._conn if self.enabled else None

    # --- slices ---------------------------------------------------------------

    def save_slice(self, config: SliceConfig) -> None:
        """Insert or replace a slice configuration."""
        db = self._db
        if db is None:
            return
        payload = config.model_dump_json()
        with self._lock:
            db.execute(
                """
                INSERT INTO slices (slice_id, payload, status, sst, sd, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slice_id) DO UPDATE SET
                    payload = excluded.payload,
                    status = excluded.status,
                    sst = excluded.sst,
                    sd = excluded.sd,
                    updated_at = excluded.updated_at
                """,
                (
                    config.slice_id,
                    payload,
                    config.status,
                    config.sst,
                    config.sd,
                    config.created_at.isoformat(),
                    (config.updated_at or datetime.now().astimezone()).isoformat(),
                ),
            )
            db.commit()

    def save_slices(self, configs: Iterable[SliceConfig]) -> None:
        """Persist several slices in one transaction."""
        for config in configs:
            self.save_slice(config)

    def delete_slice(self, slice_id: str) -> bool:
        """Remove a slice. Returns True when a row was actually deleted."""
        db = self._db
        if db is None:
            return False
        with self._lock:
            cursor = db.execute("DELETE FROM slices WHERE slice_id = ?", (slice_id,))
            db.commit()
            return cursor.rowcount > 0

    def load_slices(self) -> list[SliceConfig]:
        """Read every persisted slice, skipping rows that no longer validate."""
        db = self._db
        if db is None:
            return []
        with self._lock:
            rows = db.execute("SELECT payload FROM slices ORDER BY created_at").fetchall()

        slices: list[SliceConfig] = []
        for row in rows:
            try:
                slices.append(SliceConfig.model_validate_json(row["payload"]))
            except Exception as exc:
                # A schema change should degrade to "ignore that row", never a crash.
                logger.warning("Skipping unreadable slice row: %s", exc)
        return slices

    def count_slices(self) -> int:
        db = self._db
        if db is None:
            return 0
        with self._lock:
            return int(db.execute("SELECT COUNT(*) AS n FROM slices").fetchone()["n"])

    # --- audit events ----------------------------------------------------------

    def append_event(self, event: AuditEvent) -> None:
        """Append one event to the durable journal."""
        db = self._db
        if db is None:
            return
        with self._lock:
            db.execute(
                """
                INSERT OR REPLACE INTO audit_events
                    (event_id, event_type, severity, slice_id, timestamp, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type,
                    event.severity,
                    event.slice_id,
                    event.timestamp.isoformat(),
                    event.model_dump_json(),
                ),
            )
            db.commit()

    def load_events(
        self,
        limit: int = 100,
        slice_id: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
    ) -> list[AuditEvent]:
        """Read the journal newest-first, optionally filtered."""
        db = self._db
        if db is None:
            return []

        query = "SELECT payload FROM audit_events"
        clauses: list[str] = []
        params: list[object] = []
        if slice_id:
            clauses.append("slice_id = ?")
            params.append(slice_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = db.execute(query, params).fetchall()

        events: list[AuditEvent] = []
        for row in rows:
            try:
                events.append(AuditEvent.model_validate_json(row["payload"]))
            except Exception as exc:
                logger.warning("Skipping unreadable audit row: %s", exc)
        return events

    def prune_events(self, keep: int = 5000) -> int:
        """Trim the journal to the newest ``keep`` events. Returns rows removed."""
        db = self._db
        if db is None:
            return 0
        with self._lock:
            cursor = db.execute(
                """
                DELETE FROM audit_events WHERE event_id NOT IN (
                    SELECT event_id FROM audit_events ORDER BY timestamp DESC LIMIT ?
                )
                """,
                (keep,),
            )
            db.commit()
            return cursor.rowcount

    # --- maintenance -------------------------------------------------------------

    def reset(self) -> None:
        """Drop all rows. Used by tests and the demo reset endpoint."""
        db = self._db
        if db is None:
            return
        with self._lock:
            db.execute("DELETE FROM slices")
            db.execute("DELETE FROM audit_events")
            db.commit()

    def stats(self) -> dict:
        """Report storage health for the system-info endpoint."""
        db = self._db
        if db is None:
            # Either never enabled, or closed (e.g. during shutdown/tests) -
            # report as unavailable rather than crashing on a null connection.
            return {"enabled": False}
        size = self.path.stat().st_size if self.path.exists() else 0
        with self._lock:
            events = int(db.execute("SELECT COUNT(*) AS n FROM audit_events").fetchone()["n"])
            schema_version = current_version(db)
        return {
            "enabled": True,
            "path": str(self.path),
            "size_bytes": size,
            "slices": self.count_slices(),
            "events": events,
            "schema_version": schema_version,
            "schema_latest": LATEST_VERSION,
        }


_store: SqliteStore | None = None


def get_store() -> SqliteStore:
    """Return the process-wide store singleton."""
    global _store
    if _store is None:
        _store = SqliteStore()
    return _store
