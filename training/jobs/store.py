"""Transactional queue; one machine-wide OS lock across all worktrees."""

import json
import os
import sqlite3
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from training.jobs.model import JobSpec


def home() -> Path:
    return Path.home() / ".clavis" / "jobs"


@contextmanager
def worker_lock(path: Path | None = None) -> Iterator[None]:
    lock = path or home().parent / "worker.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Queue:
    def __init__(self, root: Path | None = None):
        self.root = (root or home()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, spec TEXT, "
                "status TEXT, wall REAL DEFAULT 0, pid INTEGER, born REAL, reason TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY, paused INTEGER)"
            )
            db.execute("INSERT OR IGNORE INTO control VALUES (1, 0)")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.root / "queue.sqlite3", timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def submit(self, spec: JobSpec) -> str:
        if not Path(spec.cwd).is_absolute() or not Path(spec.cwd).is_dir():
            raise ValueError("cwd must be an existing absolute directory")
        job_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute(
                "INSERT INTO jobs(id,spec,status) VALUES (?,?,'queued')",
                (job_id, spec.model_dump_json()),
            )
        return job_id

    def rows(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY rowid")]

    def paused(self) -> bool:
        with self.connect() as db:
            return bool(db.execute("SELECT paused FROM control WHERE id=1").fetchone()[0])

    def pause(self) -> None:
        with self.connect() as db:
            db.execute("UPDATE control SET paused=1 WHERE id=1")

    def resume(self) -> None:
        with self.connect() as db:
            db.execute("UPDATE control SET paused=0 WHERE id=1")
            db.execute("UPDATE jobs SET status='queued' WHERE status='paused'")

    def claim(self) -> dict[str, Any] | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT paused FROM control WHERE id=1").fetchone()[0]:
                return None
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='running' WHERE id=?", (row["id"],))
            return dict(row)

    def update(self, job_id: str, **values: Any) -> None:
        if not values.keys() <= {"status", "wall", "pid", "born", "reason"}:
            raise ValueError("invalid queue column")
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?",
                (*values.values(), job_id),
            )

    def record(self, record: dict[str, Any]) -> None:
        with (self.root / "experiments.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
