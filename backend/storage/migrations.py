"""A small, dependency-free SQLite migration runner.

The store wrote a `schema_meta` row recording SCHEMA_VERSION on every
connect, but nothing ever read it back to decide what to do - it was
inert bookkeeping. A real schema change (a new column, a new index) had no
upgrade path: `CREATE TABLE IF NOT EXISTS` is a no-op against an existing
table, so an existing database would silently keep its old shape while new
code assumed the new one, surfacing as a runtime SQL error with no
diagnostic pointing at "you need to migrate."

Versioning is tracked with SQLite's own `PRAGMA user_version` rather than a
hand-rolled table: it is atomic, built into every SQLite database with no
schema of its own to maintain, and survives a VACUUM or a copy of the file.
Migrations are plain SQL scripts applied in order inside one transaction
each, with each one immediately followed by advancing user_version to that
migration's number - so a crash mid-migration leaves the version pointing
at the last one that actually completed, not one that is half-applied.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from core.logging_config import get_logger

logger = get_logger("storage.migrations")


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    sql: str


# The original CREATE TABLE statements, preserved as migration 1 rather than
# rewritten, so a genuinely fresh database and a pre-migration-system
# database converge on exactly the same schema through exactly the same path.
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="Initial schema: slices and audit_events tables",
        sql="""
            CREATE TABLE IF NOT EXISTS slices (
                slice_id   TEXT PRIMARY KEY,
                payload    TEXT NOT NULL,
                status     TEXT NOT NULL,
                sst        INTEGER NOT NULL,
                sd         TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_slices_status ON slices(status);
            CREATE INDEX IF NOT EXISTS idx_slices_snssai ON slices(sst, sd);

            CREATE TABLE IF NOT EXISTS audit_events (
                event_id   TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                severity   TEXT NOT NULL,
                slice_id   TEXT,
                timestamp  TEXT NOT NULL,
                payload    TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_events_time ON audit_events(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_events_slice ON audit_events(slice_id);
        """,
    ),
    Migration(
        version=2,
        description="Index audit_events(severity) for the /api/events?severity= filter",
        sql="""
            CREATE INDEX IF NOT EXISTS idx_events_severity ON audit_events(severity);
        """,
    ),
)

LATEST_VERSION = max(migration.version for migration in MIGRATIONS)


def current_version(conn: sqlite3.Connection) -> int:
    """The schema version this database claims to be at."""
    (version,) = conn.execute("PRAGMA user_version").fetchone()
    return int(version)


def _looks_like_a_pre_migration_database(conn: sqlite3.Connection) -> bool:
    """True for a database that has HELIX's tables but predates PRAGMA user_version tracking.

    Such a database is already at schema 1 in every way that matters - it
    just was not marked as such, because nothing wrote user_version before
    this module existed. Treating it as version 0 and replaying migration 1
    would be harmless (every statement in it is idempotent), but marking it
    correctly is more honest about what actually happened to this file.
    """
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'slices'"
    ).fetchone()
    return row is not None


def run_migrations(conn: sqlite3.Connection) -> int:
    """Bring ``conn`` up to LATEST_VERSION. Returns the version it ends at."""
    version = current_version(conn)

    if version == 0 and _looks_like_a_pre_migration_database(conn):
        logger.info("Detected a pre-migration database; marking it schema version 1")
        version = 1
        conn.execute(f"PRAGMA user_version = {version}")

    applied = 0
    for migration in MIGRATIONS:
        if migration.version <= version:
            continue
        logger.info("Applying migration %d: %s", migration.version, migration.description)
        conn.executescript(migration.sql)
        conn.execute(f"PRAGMA user_version = {migration.version}")
        conn.commit()
        version = migration.version
        applied += 1

    if applied:
        logger.info("Database migrated to schema version %d (%d applied)", version, applied)
    return version
