"""[CREDENTIALED] Packaging: turn a gated story into platform-ready metadata.

For each published story this produces the hook, the title, the burned-in caption
script, the description (standard template), hashtags/keywords, and the pinned tl;dr
-- per format ("cited60", "receipts", "tool_drop", "the_number", "longform").

BUILD NOTE: scaffolded to signature. The deterministic skeleton (slots + the standard
description template) is here; the copy generation is the credentialed model call.
"""
from __future__ import annotations
import os

FORMATS = ("cited60", "receipts", "tool_drop", "the_number", "longform")

DESCRIPTION_TEMPLATE = (
    "{summary}\n\n"
    "Sources:\n{sources}\n\n"
    "Audit log: {audit_url}\n"
    "Open source: {repo_url}\n\n"
    "Cited is a fully autonomous AI newsroom. Every claim is sourced. "
    "Every editorial decision is logged and publicly auditable."
)


def package(story: dict, persona: dict, fmt: str = "cited60") -> dict:
    """Return {hook, title, caption_script, description, hashtags, pinned_tldr, fmt}."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set: copy generation is credentialed")
    raise NotImplementedError(
        "BUILD: generate hook/title/captions with the model. "
        "Fill DESCRIPTION_TEMPLATE from the story.")
