"""Command line interface:  python -m taskagent <command>"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from datetime import datetime

import config
from briefing import morning_briefing, run_report, save_report
from store import PRIORITY_ORDER, REPEATS, TaskStore


def _store() -> TaskStore:
    config.ensure_dirs()
    return TaskStore(config.TASKS_FILE)


def cmd_add(a) -> None:
    t = _store().add(a.title, a.desc or "", a.priority, a.due, a.repeat)
    print(f"added {t.id}: {t.title}")


def cmd_list(a) -> None:
    tasks = _store().load()
    if a.status:
        tasks = [t for t in tasks if t.status == a.status]
    if not tasks:
        print("(no tasks)")
        return
    print(f"{'id':<9}{'status':<9}{'prio':<8}{'due':<12}{'repeat':<10}title")
    for t in sorted(tasks, key=lambda t: (PRIORITY_ORDER[t.priority], t.due or "9999")):
        print(f"{t.id:<9}{t.status:<9}{t.priority:<8}{(t.due or '-'):<12}{(t.repeat or '-'):<10}{t.title}")


def cmd_show(a) -> None:
    t = _store().get(a.id)
    for k, v in t.__dict__.items():
        print(f"{k:>9}: {v}")


def cmd_remove(a) -> None:
    _store().remove(a.id)
    print("removed", a.id)


def cmd_reset(a) -> None:
    s = _store()
    t = s.get(a.id)
    t.status, t.attempts = "pending", 0
    s.update(t)
    print("reset", a.id)


def cmd_brief(a) -> None:
    text = morning_briefing(_store())
    print(text)
    if a.save:
        print("saved ->", save_report(text, "briefing"))


def _run(limit, verbose=True) -> None:
    from agent import process_queue
    started = datetime.now()
    results = process_queue(_store(), limit=limit, verbose=verbose)
    if not results:
        print("nothing to run")
        return
    path = save_report(run_report(results, started), "report")
    print(f"\n{sum(r.ok for _, r in results)}/{len(results)} succeeded. report -> {path}")


def cmd_run(a) -> None:
    if a.id:  # run one specific task now, regardless of due date
        from agent import run_one
        s = _store()
        started = datetime.now()
        t = s.get(a.id)
        res = run_one(s, t)
        print("\n" + res.summary)
        print("report ->", save_report(run_report([(t, res)], started), "report"))
    else:
        _run(a.limit)


def cmd_daily(a) -> None:
    """Briefing first, then work the queue."""
    text = morning_briefing(_store())
    print(text)
    save_report(text, "briefing")
    _run(a.limit)


def cmd_daemon(a) -> None:
    """Stay resident and run `daily` once a day at TASKAGENT_DAILY_TIME (HH:MM, local)."""
    print(f"daemon started; daily run at {config.DAILY_TIME}. Ctrl-C to stop.")
    last = None
    while True:
        now = datetime.now()
        if f"{now:%H:%M}" == config.DAILY_TIME and last != now.date():
            last = now.date()
            try:
                cmd_daily(a)
            except Exception as e:
                print("daily run failed:", e, file=sys.stderr)
        time.sleep(20)


def cmd_cron(_a) -> None:
    py = sys.executable
    h, m = config.DAILY_TIME.split(":")
    print("# add with `crontab -e` (Linux/macOS):")
    main_py = Path(__file__).resolve().parent / "main.py"
    print(f"{int(m)} {int(h)} * * * cd {config.HOME} && ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY {py} {main_py} daily >> {config.HOME}/cron.log 2>&1")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="taskagent", description="AI agent that works through your daily task queue.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("add", help="add a task"); s.set_defaults(fn=cmd_add)
    s.add_argument("title"); s.add_argument("-d", "--desc", help="details / acceptance criteria")
    s.add_argument("-p", "--priority", choices=list(PRIORITY_ORDER), default="medium")
    s.add_argument("--due", help="YYYY-MM-DD"); s.add_argument("--repeat", choices=[r for r in REPEATS if r])

    s = sub.add_parser("list", help="list tasks"); s.set_defaults(fn=cmd_list)
    s.add_argument("--status")
    s = sub.add_parser("show", help="show one task incl. result"); s.set_defaults(fn=cmd_show); s.add_argument("id")
    s = sub.add_parser("remove", help="delete a task"); s.set_defaults(fn=cmd_remove); s.add_argument("id")
    s = sub.add_parser("reset", help="set a task back to pending"); s.set_defaults(fn=cmd_reset); s.add_argument("id")
    s = sub.add_parser("brief", help="print today's briefing"); s.set_defaults(fn=cmd_brief); s.add_argument("--save", action="store_true")
    s = sub.add_parser("run", help="work the queue (or one task by id)"); s.set_defaults(fn=cmd_run)
    s.add_argument("id", nargs="?"); s.add_argument("--limit", type=int)
    s = sub.add_parser("daily", help="briefing + run queue"); s.set_defaults(fn=cmd_daily); s.add_argument("--limit", type=int)
    s = sub.add_parser("daemon", help="run `daily` every day at TASKAGENT_DAILY_TIME"); s.set_defaults(fn=cmd_daemon, limit=None)
    s = sub.add_parser("cron", help="print a crontab line"); s.set_defaults(fn=cmd_cron)
    return p


def main(argv=None) -> None:
    a = build_parser().parse_args(argv)
    try:
        a.fn(a)
    except KeyError as e:
        sys.exit(f"no such task: {e}")
    except (ValueError, PermissionError) as e:
        sys.exit(f"error: {e}")
