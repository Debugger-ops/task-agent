"""Grok (xAI) backend. xAI's API is OpenAI-compatible, so we call it with httpx directly (no extra deps)."""
from __future__ import annotations

import json
import os

import httpx

import config, tools

BASE_URL = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")


def _tools() -> list[dict]:
    out = []
    for s in tools.tool_schemas():
        if "input_schema" not in s:      # skip Anthropic-only server tool (web_search); fetch_url covers browsing
            continue
        out.append({"type": "function", "function": {
            "name": s["name"], "description": s["description"], "parameters": s["input_schema"]}})
    return out


def run_loop(system: str, prompt: str, verbose: bool = True) -> tuple[bool, str, int]:
    key = os.environ.get("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY is not set")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    schemas = _tools()
    for step in range(1, config.MAX_STEPS + 1):
        r = httpx.post(f"{BASE_URL}/chat/completions", timeout=120,
                       headers={"Authorization": f"Bearer {key}"},
                       json={"model": config.XAI_MODEL, "messages": messages, "tools": schemas,
                             "max_tokens": config.MAX_TOKENS})
        if r.status_code != 200:
            raise RuntimeError(f"xAI API {r.status_code}: {r.text[:300]}")
        msg = r.json()["choices"][0]["message"]
        messages.append({k: v for k, v in msg.items() if v is not None})
        calls = msg.get("tool_calls") or []
        if not calls:
            text = (msg.get("content") or "").strip()
            ok = not any(l.strip().upper().startswith("BLOCKED:") for l in text.splitlines())
            return ok, text or "(no output)", step
        for c in calls:
            name, raw = c["function"]["name"], c["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw)
            except json.JSONDecodeError:
                args = {}
            if verbose:
                print(f"   -> {name}({raw[:120]})")
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": tools.execute(name, args)})
    return False, f"Stopped: exceeded {config.MAX_STEPS} steps without finishing.", config.MAX_STEPS
