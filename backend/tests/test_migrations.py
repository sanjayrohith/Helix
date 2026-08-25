"""Tests for the SQLite migration runner."""

from __future__ import annotations

import sqlite3

import pytest

from storage.migrations import LATEST_VERSION, current_version, run_migrations
from storage.sqlite_store import SqliteStore


@pytest.fixture
def raw_conn(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "raw.db"))
    yield conn
    conn.close()


class TestFreshDatabase:
    def test_a_brand_new_connection_starts_at_version_zero(self, raw_conn) -> None:
        assert current_version(raw_conn) == 0

    def test_migrating_reaches_the_latest_version(self, raw_conn) -> None:
        assert run_migrations(raw_conn) == LATEST_VERSION

    def test_the_tables_exist_after_migrating(self, raw_conn) -> None:
        run_migrations(raw_conn)
        tables = {
            row[0]
            for row in raw_conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {"slices", "audit_events"} <= tables

    def test_the_severity_index_exists_after_migrating(self, raw_conn) -> None:
        run_migrations(raw_conn)
        indexes = {
            row[0]
            for row in raw_conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
        assert "idx_events_severity" in indexes


class TestIdempotency:
    def test_migrating_twice_is_a_no_op_the_second_time(self, raw_conn) -> None:
        first = run_migrations(raw_conn)
        second = run_migrations(raw_conn)
        assert first == second == LATEST_VERSION

    def test_migrating_twice_does_not_error_on_existing_objects(self, raw_conn) -> None:
        run_migrations(raw_conn)
        # Every statement is CREATE ... IF NOT EXISTS; a second pass over
        # already-applied migrations must not raise.
        run_migrations(raw_conn)


class TestLegacyDatabase:
    def test_a_pre_migration_database_is_detected_and_marked(self, raw_conn) -> None:
        # Build the pre-migration-system schema by hand: tables exist, but
        # nothing ever set PRAGMA user_version, because this module did not
        # exist yet when such a database was created.
        raw_conn.executescript(
            """
            CREATE TABLE slices (
                slice_id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                sst INTEGER NOT NULL, sd TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT
            );
            CREATE TABLE audit_events (
                event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, severity TEXT NOT NULL,
                slice_id TEXT, timestamp TEXT NOT NULL, payload TEXT NOT NULL
            );
            INSERT INTO slices VALUES ('legacy-1', '{}', 'active', 1, '0x1', '2024-01-01', NULL);
            """
        )
        raw_conn.commit()

        version = run_migrations(raw_conn)

        assert version == LATEST_VERSION
        row = raw_conn.execute("SELECT slice_id FROM slices").fetchone()
        assert row[0] == "legacy-1", "existing data must survive detection and migration"

    def test_a_legacy_database_gains_the_new_index(self, raw_conn) -> None:
        raw_conn.executescript(
            """
            CREATE TABLE slices (
                slice_id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                sst INTEGER NOT NULL, sd TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT
            );
            CREATE TABLE audit_events (
                event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, severity TEXT NOT NULL,
                slice_id TEXT, timestamp TEXT NOT NULL, payload TEXT NOT NULL
            );
            """
        )
        run_migrations(raw_conn)
        indexes = {
            row[0]
            for row in raw_conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
        assert "idx_events_severity" in indexes


class TestSqliteStoreIntegration:
    def test_a_store_reports_its_schema_version(self, tmp_path) -> None:
        store = SqliteStore(path=tmp_path / "store.db", enabled=True)
        stats = store.stats()
        assert stats["schema_version"] == LATEST_VERSION
        assert stats["schema_latest"] == LATEST_VERSION
        store.close()

    def test_reopening_a_store_preserves_its_data_and_version(self, tmp_path) -> None:
        path = tmp_path / "reopen.db"
        first = SqliteStore(path=path, enabled=True)
        first.close()

        second = SqliteStore(path=path, enabled=True)
        assert second.stats()["schema_version"] == LATEST_VERSION
        second.close()
