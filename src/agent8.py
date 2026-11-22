"""Session 2's agent loop, wired to the tool server (unchanged in spirit)."""
from __future__ import annotations

import json

INSTRUCTIONS = (
    "You are an integration agent. Reply with ONLY JSON.\n"
    'Tool: {"action": "<tool>", "args": {...}}  Finish: {"final": "<answer>"}\n'
    "Tools:\n{catalog}"
)


def est_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _parse(reply: str) -> dict:
    t = reply.strip()
    i, j = t.find("{"), t.rfind("}")
    if i == -1:
        return {"final": t}
    return json.loads(t[i:j + 1])


def run_agent(llm, server, task: str, max_steps: int = 8):
    history = [f"TASK: {task}"]
    trace = []
    for step in range(1, max_steps + 1):
        prompt = (INSTRUCTIONS.replace("{catalog}", server.catalog_text())
                  + "\n\n" + "\n".join(history))
        decision = _parse(llm.generate(prompt))
        trace.append({"step": step, "decision": decision})
        if "final" in decision:
            return decision["final"], trace
        try:
            obs = server.call_tool(decision.get("action", ""),
                                   decision.get("args", {}))
        except Exception as ex:  # noqa: BLE001 — honest observations
            obs = f"ERROR: {ex}"
        trace.append({"step": step, "observation": obs})
        history.append(f"ACTION: {json.dumps(decision)}")
        history.append(f"OBSERVATION: {json.dumps(obs, default=str)}")
    return "stopped: max steps", trace
