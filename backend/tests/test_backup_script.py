"""Tests for scripts/backup_db.py."""

from __future__ import annotations

import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

import backup_db  # noqa: E402

from models.slice_models import SliceConfig
from storage.sqlite_store import SqliteStore


def seed(path: Path) -> SqliteStore:
    store = SqliteStore(path=path, enabled=True)
    store.save_slice(
        SliceConfig(
            slice_id=str(uuid.uuid4()),
            name="Backup Test",
            sst=1,
            sd="0x00bb00",
            qos_5qi=9,
            arp_priority=5,
            guaranteed_bitrate_mbps=50.0,
            max_bitrate_mbps=100.0,
            latency_ms=20,
            security_level="standard",
            isolation="shared",
            device_count=10,
            use_case="iot",
            location="Testville",
            status="active",
        )
    )
    return store


class TestBackup:
    def test_backing_up_a_missing_database_exits_with_an_error(self, tmp_path) -> None:
        with pytest.raises(SystemExit):
            backup_db.backup(tmp_path / "nope.db", tmp_path / "out.db")

    def test_a_backup_is_a_real_readable_database(self, tmp_path) -> None:
        source = tmp_path / "source.db"
        seed(source).close()

        backup_db.backup(source, tmp_path / "backup.db")

        conn = sqlite3.connect(str(tmp_path / "backup.db"))
        count = conn.execute("SELECT COUNT(*) FROM slices").fetchone()[0]
        conn.close()
        assert count == 1

    def test_a_backup_is_independent_of_the_source_afterward(self, tmp_path) -> None:
        source = tmp_path / "source.db"
        store = seed(source)
        backup_db.backup(source, tmp_path / "backup.db")
        store.close()

        # Mutate the source after backing it up.
        store2 = SqliteStore(path=source, enabled=True)
        store2.reset()
        store2.close()

        conn = sqlite3.connect(str(tmp_path / "backup.db"))
        count = conn.execute("SELECT COUNT(*) FROM slices").fetchone()[0]
        conn.close()
        assert count == 1, "the backup must not be affected by later changes to the source"


class TestVerify:
    def test_verifying_a_missing_file_exits_with_an_error(self, tmp_path) -> None:
        with pytest.raises(SystemExit):
            backup_db.verify(tmp_path / "nope.db")

    def test_verifying_a_healthy_database_does_not_raise(self, tmp_path) -> None:
        path = tmp_path / "healthy.db"
        seed(path).close()
        backup_db.verify(path)  # must not raise

    def test_verifying_a_corrupt_file_exits_with_an_error(self, tmp_path) -> None:
        path = tmp_path / "corrupt.db"
        path.write_bytes(b"this is not a sqlite database")
        with pytest.raises(SystemExit):
            backup_db.verify(path)


class TestRestore:
    def test_restore_refuses_to_overwrite_without_force(self, tmp_path) -> None:
        backup_path = tmp_path / "backup.db"
        seed(backup_path).close()
        existing = tmp_path / "existing.db"
        seed(existing).close()

        with pytest.raises(SystemExit):
            backup_db.restore(backup_path, existing, force=False)

    def test_restore_with_force_overwrites(self, tmp_path) -> None:
        backup_path = tmp_path / "backup.db"
        seed(backup_path).close()
        target = tmp_path / "target.db"
        seed(target).close()  # pre-existing, different database

        backup_db.restore(backup_path, target, force=True)

        conn = sqlite3.connect(str(target))
        count = conn.execute("SELECT COUNT(*) FROM slices").fetchone()[0]
        conn.close()
        assert count == 1

    def test_restore_to_a_fresh_path_needs_no_force(self, tmp_path) -> None:
        backup_path = tmp_path / "backup.db"
        seed(backup_path).close()
        target = tmp_path / "brand_new.db"

        backup_db.restore(backup_path, target, force=False)  # must not raise
        assert target.exists()

    def test_restoring_a_corrupt_backup_is_rejected_before_touching_the_target(
        self, tmp_path
    ) -> None:
        bad_backup = tmp_path / "bad.db"
        bad_backup.write_bytes(b"not a database")
        target = tmp_path / "target.db"

        with pytest.raises(SystemExit):
            backup_db.restore(bad_backup, target, force=True)
        assert not target.exists()

    def test_restore_clears_stale_wal_files_from_the_target(self, tmp_path) -> None:
        backup_path = tmp_path / "backup.db"
        seed(backup_path).close()
        target = tmp_path / "target.db"
        target.write_bytes(b"placeholder")
        (target.with_name(target.name + "-wal")).write_bytes(b"stale wal")
        (target.with_name(target.name + "-shm")).write_bytes(b"stale shm")

        backup_db.restore(backup_path, target, force=True)

        assert not target.with_name(target.name + "-wal").exists()
        assert not target.with_name(target.name + "-shm").exists()


class TestTimestampedPath:
    def test_includes_the_database_stem(self, tmp_path) -> None:
        db_path = tmp_path / "helix.db"
        result = backup_db.timestamped_backup_path(db_path)
        assert result.name.startswith("helix-")
        assert result.parent.name == "backups"
