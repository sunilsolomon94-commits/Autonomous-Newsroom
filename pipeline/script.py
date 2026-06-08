"""Scripting agent: write Mira's anchor read from verified claims. Credentialed."""
from __future__ import annotations
import os


def write(event, claims, persona: dict) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set: scripting is credentialed")
    from pipeline import llm
    a = persona["anchor"]
    system = (
        f"You write the anchor read for {persona['channel']['name']}, delivered by {a['name']}. "
        f"Style: {a['style']} Structure: open with the cold-open hook (the sharpest sourced claim), "
        f"then this exact disclosure line: \"{a['disclosure_line']}\" Then context, then the claims, "
        "each cited inline by publisher name (e.g. 'according to TechCrunch'), a brief precedent "
        "block, and a close on what to watch next. Use ONLY the provided claims; never add facts. "
        "Never quote more than 15 verbatim words from any single source. No editorializing "
        "adjectives; report magnitude with numbers, not tone. Length: 350-450 words.")
    src_names = {it["id"]: it.get("publisher", it["id"]) for it in event.items}
    claim_lines = "\n".join(
        f'- "{c.text}" (sources: {", ".join(src_names.get(s, s) for s in c.source_ids)})'
        for c in claims)
    user = (f"TOPIC: {event.items[0].get('title', '')}\n\n"
            f"VERIFIED CLAIMS:\n{claim_lines}\n\nWrite the anchor script.")
    return llm.complete(system, user, model=llm.SONNET, max_tokens=1100)
