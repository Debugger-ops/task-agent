"""Central configuration. Everything is overridable via environment variables."""
from __future__ import annotations

import os
from pathlib import Path

HOME = Path(os.environ.get("TASKAGENT_HOME", Path.home() / ".taskagent")).expanduser()
WORKSPACE = Path(os.environ.get("TASKAGENT_WORKSPACE", HOME / "workspace")).expanduser()
TASKS_FILE = Path(os.environ.get("TASKAGENT_TASKS", HOME / "tasks.json")).expanduser()
REPORTS_DIR = Path(os.environ.get("TASKAGENT_REPORTS", HOME / "reports")).expanduser()
NOTES_FILE = WORKSPACE / "notes.md"

PROVIDER = os.environ.get("TASKAGENT_PROVIDER", "anthropic")  # "anthropic" or "xai" (Grok)
XAI_MODEL = os.environ.get("TASKAGENT_XAI_MODEL", "grok-4")
MODEL = os.environ.get("TASKAGENT_MODEL", "claude-sonnet-4-5")
MAX_TOKENS = int(os.environ.get("TASKAGENT_MAX_TOKENS", "4096"))
MAX_STEPS = int(os.environ.get("TASKAGENT_MAX_STEPS", "25"))        # tool-loop iterations per task
SHELL_TIMEOUT = int(os.environ.get("TASKAGENT_SHELL_TIMEOUT", "30"))  # seconds
MAX_TOOL_OUTPUT = int(os.environ.get("TASKAGENT_MAX_TOOL_OUTPUT", "8000"))  # chars returned to model
ALLOW_SHELL = os.environ.get("TASKAGENT_ALLOW_SHELL", "1") == "1"
CONFIRM_SHELL = os.environ.get("TASKAGENT_CONFIRM_SHELL", "1") == "1"  # ask y/n before each command
WEB_SEARCH_MAX_USES = int(os.environ.get("TASKAGENT_WEB_SEARCH_MAX_USES", "5"))
DAILY_TIME = os.environ.get("TASKAGENT_DAILY_TIME", "09:00")  # used by `taskagent daemon`


def ensure_dirs() -> None:
    for p in (HOME, WORKSPACE, REPORTS_DIR):
        p.mkdir(parents=True, exist_ok=True)
