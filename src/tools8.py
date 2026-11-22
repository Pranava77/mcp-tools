"""The four integration tools, registered on the server. Reads free, writes
gated (write=True -> blocked in dry-run; idempotency enforced server-side)."""
from __future__ import annotations

from . import fakes
from .tool_server import ToolServer


def build_server(dry_run: bool = False) -> ToolServer:
    server = ToolServer(dry_run=dry_run)

    @server.tool("get_pr",
                 "Fetch a pull request by id (title, author, diff). Use FIRST.",
                 {"pr_id": "int"})
    def get_pr(pr_id: int):
        pr = fakes.GITEA.prs.get(pr_id)
        return pr if pr else {"error": f"no PR {pr_id}"}

    @server.tool("list_issues",
                 "List tracker issues. Use BEFORE create_issue to avoid duplicates.",
                 {})
    def list_issues():
        return [{"id": i["id"], "title": i["title"]}
                for i in fakes.TRACKER.issues]

    @server.tool("create_issue",
                 "Create ONE tracker issue. Never for duplicates — "
                 "check list_issues first. Title <= 80 chars.",
                 {"title": "str", "body": "str", "labels": "list[str]"},
                 write=True)
    def create_issue(title: str, body: str, labels=()):
        # Idempotency: if an open issue with this title already exists, return it
        for issue in fakes.TRACKER.issues:
            if issue["title"] == title and issue.get("open", True):
                return {"status": "exists", "id": issue["id"]}
        # Otherwise create a new one
        issue = fakes.TRACKER.create(title, body, labels)
        return {"status": "created", "id": issue["id"]}

    @server.tool("post_message",
                 "Post ONE short message to a chat channel.",
                 {"channel": "str", "text": "str"},
                 write=True)
    def post_message(channel: str, text: str):
        fakes.CHAT.post(channel, text)
        return {"status": "posted", "channel": channel}

    return server
