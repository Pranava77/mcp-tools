from src import fakes
from src.agent8 import run_agent
from src.llm_client import FakeLLMClient
from src.main import SCRIPT, TASK
from src.tools8 import build_server


def setup_function(_):
    fakes.reset()


def test_full_flow_pr_to_issue_to_chat():
    server = build_server()
    llm = FakeLLMClient(scripted=list(SCRIPT))
    answer, trace = run_agent(llm, server, TASK)
    assert "triaged" in answer
    assert len(fakes.TRACKER.issues) == 1
    assert fakes.TRACKER.issues[0]["title"].startswith("PR7:")
    assert len(fakes.CHAT.messages) == 1
    assert fakes.CHAT.messages[0]["channel"] == "#eng"
    # trace shows reads before writes
    actions = [t["decision"].get("action") for t in trace if "decision" in t and "action" in t["decision"]]
    assert actions.index("list_issues") < actions.index("create_issue")


def test_second_run_files_no_duplicate():
    server = build_server()
    run_agent(FakeLLMClient(scripted=list(SCRIPT)), server, TASK)
    run_agent(FakeLLMClient(scripted=list(SCRIPT)), server, TASK)
    assert len(fakes.TRACKER.issues) == 1
