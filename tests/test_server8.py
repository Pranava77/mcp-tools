import pytest

from src import fakes
from src.tool_server import ToolError
from src.tools8 import build_server


def setup_function(_):
    fakes.reset()


def test_catalog_lists_four_tools_with_descriptions():
    server = build_server()
    cat = server.list_tools()
    names = {t["name"] for t in cat}
    assert names == {"get_pr", "list_issues", "create_issue", "post_message"}
    assert all(t["description"] for t in cat)


def test_unknown_tool_and_bad_args_raise():
    server = build_server()
    with pytest.raises(ToolError):
        server.call_tool("teleport", {})
    with pytest.raises(ToolError):
        server.call_tool("get_pr", {"wrong_arg": 1})


def test_create_issue_is_idempotent_by_title():
    server = build_server()
    a = server.call_tool("create_issue", {"title": "PR7: x", "body": "b", "labels": []})
    b = server.call_tool("create_issue", {"title": "PR7: x", "body": "b", "labels": []})
    assert a["status"] == "created"
    assert b["status"] == "exists" and b["id"] == a["id"]
    assert len(fakes.TRACKER.issues) == 1


def test_dry_run_blocks_writes_but_allows_reads():
    server = build_server(dry_run=True)
    pr = server.call_tool("get_pr", {"pr_id": 7})
    assert pr["id"] == 7                              # read flows
    out = server.call_tool("create_issue", {"title": "t", "body": "b", "labels": []})
    assert out["status"] == "dry-run"
    assert fakes.TRACKER.issues == []                 # nothing written
    assert any("create_issue" in p for p in server.plan)
