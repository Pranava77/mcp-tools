"""In-process fakes of the three team systems — tests fire NO live side-effects.
The lab's real self-hosted Gitea/Mattermost are the live upgrade path: same
tool code, real HTTP."""
from __future__ import annotations


class FakeGitea:
    def __init__(self):
        self.prs = {7: {
            "id": 7, "title": "Add rate limiting to checkout API",
            "author": "asha",
            "diff": ("+ limiter = RateLimiter(100/min)\n"
                     "+ @limiter.guard\n  def checkout(...):\n"
                     "- # TODO: protect this endpoint"),
        }}


class FakeTracker:
    def __init__(self):
        self.issues: list[dict] = []
        self._next = 1

    def create(self, title: str, body: str, labels=()) -> dict:
        issue = {"id": self._next, "title": title, "body": body,
                 "labels": list(labels), "open": True}
        self.issues.append(issue)
        self._next += 1
        return issue


class FakeChat:
    def __init__(self):
        self.messages: list[dict] = []

    def post(self, channel: str, text: str) -> dict:
        msg = {"channel": channel, "text": text}
        self.messages.append(msg)
        return msg


GITEA = FakeGitea()
TRACKER = FakeTracker()
CHAT = FakeChat()


def reset():
    global GITEA, TRACKER, CHAT
    GITEA = FakeGitea()
    TRACKER = FakeTracker()
    CHAT = FakeChat()
