"""Daily briefing (morning plan) and end-of-run report, written as markdown."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import config
from store import Task, TaskStore


def _row(t: Task) -> str:
    return f"| {t.id} | {t.priority} | {t.due or '-'} | {t.repeat or '-'} | {t.title} |"


def morning_briefing(store: TaskStore, today: date | None = None) -> str:
    today = today or date.today()
    tasks = store.load()
    runnable = store.runnable(today)
    overdue = [t for t in runnable if t.due and date.fromisoformat(t.due) < today]
    upcoming = sorted((t for t in tasks if t.status == "pending" and t.due and date.fromisoformat(t.due) > today),
                      key=lambda t: t.due)[:5]
    failed = [t for t in tasks if t.status == "failed"]
    hdr = "| id | priority | due | repeat | title |\n|---|---|---|---|---|"
    out = [f"# Briefing - {today:%A %d %b %Y}", "",
           f"Queue: {len(runnable)} runnable, {len(overdue)} overdue, {len(failed)} failed, "
           f"{sum(t.status == 'done' for t in tasks)} done total.", "",
           "## Plan for today (run order)", hdr, *map(_row, runnable)]
    if not runnable:
        out.append("| - | - | - | - | nothing runnable |")
    if overdue:
        out += ["", "## Overdue", hdr, *map(_row, overdue)]
    if failed:
        out += ["", "## Failed (retry with `taskagent run`)", hdr, *map(_row, failed)]
    if upcoming:
        out += ["", "## Coming up", hdr, *map(_row, upcoming)]
    return "\n".join(out) + "\n"


def run_report(results: list, started: datetime) -> str:
    ok = sum(r.ok for _, r in results)
    out = [f"# Run report - {started:%Y-%m-%d %H:%M}", "",
           f"{ok}/{len(results)} tasks succeeded.", "",
           "| id | status | steps | title |", "|---|---|---|---|"]
    out += [f"| {t.id} | {'done' if r.ok else 'FAILED'} | {r.steps} | {t.title} |" for t, r in results]
    for t, r in results:
        out += ["", f"### {t.title} ({t.id})", r.summary]
    return "\n".join(out) + "\n"


def save_report(text: str, kind: str = "report") -> Path:
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    p = config.REPORTS_DIR / f"{datetime.now():%Y-%m-%d_%H%M}_{kind}.md"
    p.write_text(text)
    return p
