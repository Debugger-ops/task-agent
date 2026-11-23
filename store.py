"""Task queue persisted as JSON. Atomic writes, simple recurrence support."""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

try:
    import fcntl
except ImportError:  # Windows: no advisory locks, fall back to no locking
    fcntl = None

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
STALE_RUNNING_MINUTES = 30
STATUSES = ("pending", "running", "done", "failed", "skipped")
REPEATS = (None, "daily", "weekdays", "weekly")


@dataclass
class Task:
    title: str
    description: str = ""
    priority: str = "medium"           # high | medium | low
    due: Optional[str] = None          # YYYY-MM-DD
    repeat: Optional[str] = None       # None | daily | weekdays | weekly
    status: str = "pending"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    last_run: Optional[str] = None
    result: Optional[str] = None
    attempts: int = 0

    def is_due(self, today: Optional[date] = None) -> bool:
        today = today or date.today()
        return self.due is None or date.fromisoformat(self.due) <= today


class TaskStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    # -- persistence -------------------------------------------------------
    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        """Exclusive cross-process lock so concurrent read-modify-write cycles can't lose updates."""
        if fcntl is None:
            yield
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path.with_suffix(".lock"), "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)

    def load(self) -> list[Task]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text() or "[]")
        return [Task(**t) for t in raw]

    def save(self, tasks: list[Task]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump([asdict(t) for t in tasks], f, indent=2)
        os.replace(tmp, self.path)

    # -- operations --------------------------------------------------------
    def add(self, title: str, description: str = "", priority: str = "medium",
            due: Optional[str] = None, repeat: Optional[str] = None) -> Task:
        if priority not in PRIORITY_ORDER:
            raise ValueError(f"priority must be one of {list(PRIORITY_ORDER)}")
        if repeat not in REPEATS:
            raise ValueError(f"repeat must be one of {REPEATS}")
        if due:
            date.fromisoformat(due)  # validate
        t = Task(title=title, description=description, priority=priority, due=due, repeat=repeat)
        with self._lock():
            tasks = self.load()
            tasks.append(t)
            self.save(tasks)
        return t

    def get(self, task_id: str) -> Task:
        for t in self.load():
            if t.id == task_id:
                return t
        raise KeyError(task_id)

    def update(self, task: Task) -> None:
        with self._lock():
            tasks = self.load()
            for i, t in enumerate(tasks):
                if t.id == task.id:
                    tasks[i] = task
                    self.save(tasks)
                    return
        raise KeyError(task.id)

    def remove(self, task_id: str) -> None:
        with self._lock():
            self.save([t for t in self.load() if t.id != task_id])

    def runnable(self, today: Optional[date] = None) -> list[Task]:
        """Pending (or failed with <3 attempts) tasks that are due, sorted by priority then due date."""
        today = today or date.today()
        out = [t for t in self.load()
               if (t.status == "pending" or (t.status == "failed" and t.attempts < 3)) and t.is_due(today)]
        return sorted(out, key=lambda t: (PRIORITY_ORDER[t.priority], t.due or "9999-12-31", t.created))

    def recover_stale(self, now: Optional[datetime] = None) -> int:
        """Tasks left `running` by a crash/kill go back to pending so they aren't stuck forever."""
        now = now or datetime.now()
        with self._lock():
            tasks, n = self.load(), 0
            for t in tasks:
                if t.status != "running":
                    continue
                started = datetime.fromisoformat(t.last_run) if t.last_run else None
                if started is None or now - started > timedelta(minutes=STALE_RUNNING_MINUTES):
                    t.status, n = "pending", n + 1
            if n:
                self.save(tasks)
        return n

    def reschedule_recurring(self, today: Optional[date] = None) -> int:
        """Reset finished recurring tasks to pending with the next due date.

        A failed task is only rescheduled once its retries are exhausted (attempts >= 3); before
        that it stays `failed` so runnable() can retry it and the attempt counter is preserved.
        """
        today = today or date.today()
        with self._lock():
            tasks, n = self.load(), 0
            for t in tasks:
                finished = t.status in ("done", "skipped") or (t.status == "failed" and t.attempts >= 3)
                if t.repeat and finished:
                    base = date.fromisoformat(t.due) if t.due else today
                    nxt = base
                    while nxt <= today or (t.repeat == "weekdays" and nxt.weekday() >= 5):
                        nxt += timedelta(days=7 if t.repeat == "weekly" else 1)
                    t.due, t.status, t.attempts = nxt.isoformat(), "pending", 0
                    n += 1
            if n:
                self.save(tasks)
        return n
