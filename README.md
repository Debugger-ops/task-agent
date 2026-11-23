# taskagent (single-folder layout)

A Python AI agent that works through a task queue you give it, every day. Built on the Anthropic API with a tool-use loop.

## Setup

```bash
cd task-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python -m pytest -q          # 25 tests, no API key needed
```

## Commands

| Command | What it does |
|---|---|
| `python main.py add "Title" -d "details" -p high --due 2026-11-02 --repeat daily` | Add a task (`-p` high/medium/low; `--repeat` daily/weekdays/weekly) |
| `python main.py list [--status pending]` | Show queue |
| `python main.py show <id>` | Full task incl. agent's result |
| `python main.py brief [--save]` | Today's briefing: run order, overdue, failed, upcoming |
| `python main.py run` | Work all due tasks (priority, then due date) |
| `python main.py run <id>` | Run one task now, ignoring due date |
| `python main.py daily` | Briefing + run queue + save report (what you schedule) |
| `python main.py daemon` | Stay resident; runs `daily` at `TASKAGENT_DAILY_TIME` |
| `python main.py cron` | Prints a crontab line for `daily` |
| `python main.py reset <id>` / `remove <id>` | Re-queue / delete |

## Tools the agent has

| Tool | Scope / limit |
|---|---|
| `read_file`, `write_file`, `list_files` | Confined to the workspace; `..`, absolute paths, symlink escapes are rejected |
| `add_note`, `read_notes` | Persistent `notes.md` = memory across tasks and days |
| `run_shell` | Runs with cwd = workspace; 30 s timeout; blocklist (sudo, `rm -rf /`, `curl\|sh`, ...); y/n confirm by default (unattended runs: set `TASKAGENT_CONFIRM_SHELL=0`) |
| `fetch_url` | http(s) only, public addresses only (localhost/private/metadata IPs blocked, redirects re-checked), HTML stripped to text, 8000-char cap, output marked untrusted |
| `web_search` | Anthropic server-side search, max 5 uses per task |

## Behavior

| Item | Rule |
|---|---|
| Run order | priority (high first) then due date then creation time |
| Loop cap | 25 model/tool steps per task (`TASKAGENT_MAX_STEPS`) |
| Failure | API/tool error or a line starting `BLOCKED:` marks task `failed`; queue continues; failed tasks retried until 3 attempts |
| Recurring | After a run, `daily`/`weekdays`/`weekly` tasks reset to `pending` with the next due date (weekends skipped for `weekdays`) |
| Reports | Markdown tables in `~/.taskagent/reports/` (briefing + run report) |

## Config (env vars)

| Var | Default |
|---|---|
| `TASKAGENT_HOME` | `~/.taskagent` (tasks.json, workspace/, reports/) |
| `TASKAGENT_MODEL` | `claude-sonnet-4-5` |
| `TASKAGENT_DAILY_TIME` | `09:00` (local) |
| `TASKAGENT_ALLOW_SHELL` / `TASKAGENT_CONFIRM_SHELL` | `1` / `1` |
| `TASKAGENT_MAX_STEPS`, `TASKAGENT_SHELL_TIMEOUT`, `TASKAGENT_WEB_SEARCH_MAX_USES` | `25`, `30`, `5` |

## Example

```bash
python main.py add "Summarize today's top 5 AI news into news.md" -p high --repeat daily
python main.py add "Draft a 7-day GATE EC revision plan in plan.md" -d "2h/day, weak: signals, EM" --due 2026-11-01
python main.py add "Write a Python script that dedupes a CSV and test it" -p low
python main.py daily
```

## Extending

Add a tool: write a function in `tools.py`, register it in `TOOLS`, add its schema in `tool_schemas()`. Email/calendar/Notion integrations fit the same way (or via MCP).

## Safety notes

The shell runs as your user; the blocklist is a guard, not a sandbox. For untrusted tasks run inside Docker/a VM, or keep `TASKAGENT_CONFIRM_SHELL=1` (default) or set `TASKAGENT_ALLOW_SHELL=0`.
# task-agent
