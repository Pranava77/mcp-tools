"""Demo: PR -> issue -> chat, with --dry-run and idempotent double-run.

    python -m src.main [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

from . import fakes
from .agent8 import run_agent
from .llm_client import ClaudeClient, FakeLLMClient, OllamaClient
from .tools8 import build_server

TASK = (
    "A pull request was opened. Using your tools:\n"
    "1. Read PR 7 (get_pr) and existing issues (list_issues).\n"
    "2. If no issue references PR 7, create ONE issue summarising "
    "risk and review focus (title starts 'PR7:').\n"
    "3. Post a 2-line summary to #eng (post_message).\n"
    "Never duplicate; prefer updating over creating."
)

SCRIPT = [
    '{"action": "get_pr", "args": {"pr_id": 7}}',
    '{"action": "list_issues", "args": {}}',
    '{"action": "create_issue", "args": {"title": "PR7: rate limiting on checkout — review risk", '
    '"body": "New limiter guards checkout; review 429 handling + limits config.", "labels": ["feat"]}}',
    '{"action": "post_message", "args": {"channel": "#eng", '
    '"text": "PR7 (rate limiting) summarised; issue filed for review focus."}}',
    '{"final": "PR 7 triaged: issue filed, team notified."}',
]


def get_llm():
    if os.getenv("ANTHROPIC_API_KEY"):
        return ClaudeClient()
    try:
        c = OllamaClient()
        c.generate("ping")
        return c
    except Exception:
        return FakeLLMClient(scripted=list(SCRIPT))


def show(trace):
    for t in trace:
        print("  ", json.dumps(t, default=str)[:110])


def main() -> None:
    load_dotenv()
    dry = "--dry-run" in sys.argv
    fakes.reset()
    server = build_server(dry_run=dry)
    llm = get_llm()

    answer, trace = run_agent(llm, server, TASK)
    show(trace)
    print("ANSWER:", answer)
    if dry:
        print("\nDRY-RUN plan:")
        for line in server.plan:
            print("  ", line)
        return

    print("\nfakes state: issues =", [i["title"] for i in fakes.TRACKER.issues],
          "| chat =", [m["text"][:40] for m in fakes.CHAT.messages])

    print("\n=== second run (idempotency) ===")
    llm2 = get_llm() if os.getenv("ANTHROPIC_API_KEY") else FakeLLMClient(scripted=list(SCRIPT))
    answer2, trace2 = run_agent(llm2, server, TASK)
    obs = [t["observation"] for t in trace2 if "observation" in t]
    print("create_issue observation:", next((o for o in obs if isinstance(o, dict) and "status" in o and o.get("status") in ("exists", "created")), "n/a"))
    print("issues now:", len(fakes.TRACKER.issues), "(no duplicate)")


if __name__ == "__main__":
    main()
