#!/usr/bin/env python3
"""Back up and restore the HELIX SQLite database.

A file copy of a SQLite database taken while the process is writing to it
can capture a torn, inconsistent snapshot - the WAL file has to be checkpointed
and the copy has to be transactionally consistent, or a "backup" is a trap
that looks fine until the day it is actually needed. This uses SQLite's own
online backup API (`sqlite3.Connection.backup`), which is exactly what it is
for: a live, consistent copy taken while the source database is in use,
with no need to stop the API server first.

Usage:
    python scripts/backup_db.py backup [--db PATH] [--out PATH]
    python scripts/backup_db.py restore --from PATH [--db PATH] [--force]
    python scripts/backup_db.py verify PATH
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from core.config import settings
from storage.migrations import LATEST_VERSION, current_version


def default_db_path() -> Path:
    return settings.database_path


def backup(db_path: Path, out_path: Path) -> None:
    if not db_path.exists():
        raise SystemExit(f"No database at {db_path}; nothing to back up.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(str(db_path))
    try:
        destination = sqlite3.connect(str(out_path))
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    version = current_version(sqlite3.connect(str(out_path)))
    size_kb = out_path.stat().st_size / 1024
    print(f"Backed up {db_path} -> {out_path} ({size_kb:.1f} KiB, schema v{version})")


def restore(source_path: Path, db_path: Path, force: bool) -> None:
    if not source_path.exists():
        raise SystemExit(f"Backup file not found: {source_path}")

    verify(source_path)

    if db_path.exists() and not force:
        raise SystemExit(
            f"{db_path} already exists. This overwrites it entirely.\n"
            "Pass --force once you are sure, ideally after backing up the current one."
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    # A plain file copy is safe here (unlike for the live backup direction):
    # the source is a backup file nothing else is writing to, and the
    # destination is not yet open by the running API process.
    shutil.copy2(source_path, db_path)

    # Drop any WAL/SHM siblings from whatever was previously at db_path -
    # they belong to the old database's write-ahead log, not the restored one.
    for suffix in ("-wal", "-shm"):
        stale = db_path.with_name(db_path.name + suffix)
        stale.unlink(missing_ok=True)

    print(f"Restored {source_path} -> {db_path}")


def verify(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"No file at {path}")

    conn = sqlite3.connect(str(path))
    try:
        try:
            # A file that is not a SQLite database at all (corrupted, or
            # never one to begin with) does not fail gracefully here - it
            # raises DatabaseError rather than returning a checkable "not
            # ok" row, so that has to be caught explicitly rather than only
            # checking the PRAGMA's result value.
            result = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise SystemExit(f"{path} is not a readable SQLite database: {exc}") from exc

        if result[0] != "ok":
            raise SystemExit(f"Integrity check failed for {path}: {result[0]}")

        try:
            version = current_version(conn)
            slice_count = conn.execute("SELECT COUNT(*) FROM slices").fetchone()[0]
            event_count = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise SystemExit(f"{path} passed integrity_check but is missing expected tables: {exc}") from exc
    finally:
        conn.close()

    status = "up to date" if version == LATEST_VERSION else f"needs migration to v{LATEST_VERSION}"
    print(
        f"{path}: OK - schema v{version} ({status}), "
        f"{slice_count} slice(s), {event_count} event(s)"
    )


def timestamped_backup_path(db_path: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return db_path.parent / "backups" / f"{db_path.stem}-{stamp}.db"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Take a consistent live backup")
    backup_parser.add_argument("--db", type=Path, default=None, help="Source database (default: configured path)")
    backup_parser.add_argument("--out", type=Path, default=None, help="Destination file (default: timestamped, alongside the database)")

    restore_parser = subparsers.add_parser("restore", help="Restore a backup, overwriting the current database")
    restore_parser.add_argument("--from", dest="source", type=Path, required=True, help="Backup file to restore from")
    restore_parser.add_argument("--db", type=Path, default=None, help="Destination database (default: configured path)")
    restore_parser.add_argument("--force", action="store_true", help="Overwrite an existing database without asking")

    verify_parser = subparsers.add_parser("verify", help="Check a database file's integrity and schema version")
    verify_parser.add_argument("path", type=Path)

    args = parser.parse_args()

    if args.command == "backup":
        db_path = args.db or default_db_path()
        out_path = args.out or timestamped_backup_path(db_path)
        backup(db_path, out_path)
    elif args.command == "restore":
        db_path = args.db or default_db_path()
        restore(args.source, db_path, args.force)
    elif args.command == "verify":
        verify(args.path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
