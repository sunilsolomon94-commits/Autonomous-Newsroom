"""Thin model-call layer for the credentialed steps. One place to route models,
parse JSON robustly, and keep token budgets capped (cost brake #2).
Haiku does the bulk work; Sonnet writes the anchor script and longer-form analysis."""
from __future__ import annotations
import json
import re

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from env
    return _client


def complete(system: str, user: str, model: str = HAIKU, max_tokens: int = 1500) -> str:
    msg = _get_client().messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def parse_json(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"(\[.*\]|\{.*\})", t, flags=re.S)
        if m:
            return json.loads(m.group(1))
        raise
