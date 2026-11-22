"""A minimal MCP-style tool server: tools/list + tools/call, in-process.

Real MCP wraps exactly this shape in JSON-RPC over stdio/HTTP (see the official
SDKs). We keep it in-process so every moving part is visible in ~40 lines.
Supports dry-run: writes are blocked and recorded as a plan.
"""
from __future__ import annotations

from typing import Callable


class ToolError(Exception):
    pass


class ToolServer:
    def __init__(self, dry_run: bool = False):
        self._tools: dict[str, dict] = {}
        self.dry_run = dry_run
        self.plan: list[str] = []        # what WOULD have run in dry-run

    def tool(self, name: str, description: str, schema: dict,
             write: bool = False) -> Callable:
        def register(fn: Callable) -> Callable:
            self._tools[name] = {"fn": fn, "description": description,
                                 "schema": schema, "write": write}
            return fn
        return register

    def list_tools(self) -> list[dict]:
        return [{"name": n, "description": t["description"],
                 "schema": t["schema"], "write": t["write"]}
                for n, t in self._tools.items()]

    def call_tool(self, name: str, args: dict):
        # 1. unknown tool -> raise ToolError
        if name not in self._tools:
            raise ToolError(f"unknown tool: {name}")

        tool = self._tools[name]

        # 2. args not in the schema -> raise ToolError
        allowed = set(tool["schema"].keys())
        provided = set(args.keys())
        if not provided.issubset(allowed):
            raise ToolError(f"unexpected args: {provided - allowed}")

        # 3. write tool + dry_run -> record in plan, return dry-run status
        if tool["write"] and self.dry_run:
            self.plan.append(f"{name}({args})")
            return {"status": "dry-run", "tool": name}

        # 4. otherwise run the function
        return tool["fn"](**args)

    def catalog_text(self) -> str:
        return "\n".join(f"- {t['name']}: {t['description']} args: {t['schema']}"
                         for t in self.list_tools())


if __name__ == "__main__":
    # Slide 14 demo:  python -m src.tool_server
    import json

    from .tools8 import build_server

    server = build_server()

    print("=== tools/list: the catalog, as data ===")
    for t in server.list_tools():
        flag = "WRITE (gated)" if t["write"] else "read (free)"
        print(f"\n- {t['name']}  [{flag}]")
        print(f"    description: {t['description']}")
        print(f"    schema:      {json.dumps(t['schema'])}")

    print("\n=== tools/call: get_pr(pr_id=7), by hand, no agent ===")
    print(json.dumps(server.call_tool("get_pr", {"pr_id": 7}), indent=2))

    print("\n=== tools/call: bad calls become honest errors ===")
    for name, args in [("delete_repo", {}), ("get_pr", {"pr_id": 7, "force": True})]:
        try:
            server.call_tool(name, args)
        except Exception as ex:  # run as __main__, ToolError is a distinct class object
            print(f"{name}({args}) -> {type(ex).__name__}: {ex}")
