"""One interface over three model tiers — plus retry/backoff and a Fake client.

    Quality  -> Claude    (ANTHROPIC_API_KEY)
    Free      -> Gemini    (GEMINI_API_KEY)
    Local     -> Ollama    (OLLAMA_BASE_URL, default http://localhost:11434)

The pipeline and router only ever see the abstract `LLMClient.generate(prompt)`,
so any tier is swappable. `FakeLLMClient` lets the whole pipeline be unit-tested
offline with zero network calls.
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.request
from typing import Callable, Iterable, List, Optional


def retry(fn: Callable, *, retries: int = 4, base: float = 0.5,
          exc: tuple = (Exception,)):
    """Call `fn` with exponential backoff + jitter. Re-raises after N attempts.

    Jitter (the random term) de-synchronises many clients so they don't all
    retry in lockstep — the 'thundering herd' problem.
    """
    for attempt in range(retries):
        try:
            return fn()
        except exc:
            if attempt == retries - 1:
                raise
            time.sleep(base * (2 ** attempt) + random.uniform(0, base))


class LLMClient:
    """Abstract client. Providers override `generate`."""

    name: str = "base"

    def generate(self, prompt: str, *, system: Optional[str] = None,
                 max_tokens: int = 1024) -> str:
        raise NotImplementedError

    def stream(self, prompt: str, *, system: Optional[str] = None,
               max_tokens: int = 1024) -> Iterable[str]:
        # Default: no true streaming — yield the whole answer once.
        yield self.generate(prompt, system=system, max_tokens=max_tokens)


class FakeLLMClient(LLMClient):
    """Deterministic client for offline tests. Returns scripted responses in
    order; records every prompt it received in `.calls`."""

    def __init__(self, name: str = "fake", scripted: Optional[List[str]] = None):
        self.name = name
        self._scripted = list(scripted or [])
        self.calls: List[str] = []

    def generate(self, prompt: str, *, system: Optional[str] = None,
                 max_tokens: int = 1024) -> str:
        self.calls.append(prompt)
        if self._scripted:
            return self._scripted.pop(0)
        return f"[fake:{self.name}] {prompt[:60]}"

    def stream(self, prompt: str, *, system: Optional[str] = None,
               max_tokens: int = 1024) -> Iterable[str]:
        for word in self.generate(prompt, system=system).split(" "):
            yield word + " "


class ClaudeClient(LLMClient):
    name = "claude"

    def __init__(self, model: Optional[str] = None):
        from anthropic import Anthropic
        self._client = Anthropic()  # reads ANTHROPIC_API_KEY
        self._model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

    def _kwargs(self, prompt, system, max_tokens):
        kw = dict(model=self._model, max_tokens=max_tokens,
                  messages=[{"role": "user", "content": prompt}])
        if system:
            kw["system"] = system
        return kw

    def generate(self, prompt, *, system=None, max_tokens=1024):
        def call():
            msg = self._client.messages.create(**self._kwargs(prompt, system, max_tokens))
            # Thinking-enabled models emit ThinkingBlocks before the text block.
            return "".join(b.text for b in msg.content if b.type == "text")
        return retry(call)

    def stream(self, prompt, *, system=None, max_tokens=1024):
        with self._client.messages.stream(**self._kwargs(prompt, system, max_tokens)) as s:
            for text in s.text_stream:
                yield text


class GeminiClient(LLMClient):
    name = "gemini"

    def __init__(self, model: Optional[str] = None):
        from google import genai
        from google.genai import types
        # Our retry() owns backoff; SDK retries on top of it stacked into
        # multi-minute hangs when Gemini returned 503 (overloaded).
        self._client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY"),
            http_options=types.HttpOptions(
                timeout=60_000,
                retry_options=types.HttpRetryOptions(attempts=1)))
        self._model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    def generate(self, prompt, *, system=None, max_tokens=1024):
        contents = prompt if not system else f"{system}\n\n{prompt}"
        return retry(lambda: self._client.models.generate_content(
            model=self._model, contents=contents).text)


class OllamaClient(LLMClient):
    name = "ollama"

    def __init__(self, model: Optional[str] = None, base: Optional[str] = None):
        self._model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        self._base = base or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def generate(self, prompt, *, system=None, max_tokens=1024):
        body = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"num_predict": max_tokens},
        }
        if system:
            body["system"] = system

        def call():
            req = urllib.request.Request(
                self._base + "/api/generate",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["response"]
        return retry(call)
