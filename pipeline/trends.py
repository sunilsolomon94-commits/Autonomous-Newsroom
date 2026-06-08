"""Trend radar: surface stories BEFORE they go mainstream.

The press cycle is a lagging indicator. This module scores clustered events on
LEADING indicators -- novelty, corroboration, and above all VELOCITY (how fast
corroboration is accelerating) -- so the pipeline can publish a sourced explainer
in the window between "a paper / repo / release dropped" and "the press wrote it up."

Pure logic: no network, no credentials. It reads the events cluster.group()
produced plus a small JSON state file that remembers how much each topic has been
seen in prior cycles, so it can compute change-over-time. Run it every cycle; it
updates the state in place.

Score (0..1, higher = more worth publishing early):
  velocity      0.40  new corroboration since last cycle (the acceleration signal)
  novelty       0.25  not already covered in recent cycles
  corroboration 0.20  distinct independent sources right now
  authority     0.15  a tier-1 / primary source is present

`rising_before_mainstream` fires when velocity is high but mainstream press
(tier-2) coverage is still thin -- the early-signal sweet spot we want to own.
"""
from __future__ import annotations
import json
import os
import re
import time
from dataclasses import dataclass, field

_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "with",
         "at", "by", "is", "are", "as", "new", "its", "it", "this", "that",
         "ai", "model", "says", "report"}


def _topic_key(title: str) -> str:
    toks = [w for w in re.findall(r"[a-z0-9]+", (title or "").lower())
            if w not in _STOP and len(w) > 2]
    return " ".join(sorted(set(toks))[:6])   # stable signature from the salient tokens


@dataclass
class TrendScore:
    event_id: str
    score: float
    velocity: float
    novelty: float
    rising_before_mainstream: bool
    reasons: list[str] = field(default_factory=list)


def _load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"topics": {}}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"topics": {}}


def _save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, separators=(",", ":"))
    os.replace(tmp, path)


def _distinct_sources(ev) -> int:
    return len({i["id"] for i in ev.items})


def _has_primary(ev) -> bool:
    return any(i.get("tier") == 1 for i in ev.items)


def _mainstream_press(ev) -> int:
    return len({i["id"] for i in ev.items if i.get("tier") == 2})


def score_events(events, state_path: str = "data/trend_state.json",
                 decay_hours: float = 48.0) -> list[TrendScore]:
    """Rank events by how worth-publishing-early they are. Updates state in place."""
    state = _load_state(state_path)
    topics = state.get("topics", {})
    now = time.time()
    out: list[TrendScore] = []

    for ev in events:
        title = ev.items[0].get("title", "") if ev.items else ""
        key = _topic_key(title)
        cur = _distinct_sources(ev)
        prior = topics.get(key, {})
        prior_count = prior.get("count", 0)
        last_seen = prior.get("ts", 0)

        # velocity = new corroboration since we last saw this topic
        delta = max(0, cur - prior_count)
        velocity = min(1.0, delta / 3.0)             # +3 distinct sources in a cycle = full

        if not prior:
            novelty = 1.0
        else:
            age_h = max(0.0, (now - last_seen) / 3600.0)
            novelty = min(1.0, age_h / decay_hours) * 0.6   # seen-before is capped

        corro = min(1.0, cur / 4.0)
        authority = 1.0 if _has_primary(ev) else 0.0
        score = 0.40 * velocity + 0.25 * novelty + 0.20 * corro + 0.15 * authority

        press = _mainstream_press(ev)
        rising = velocity >= 0.5 and press <= 1
        reasons: list[str] = []
        if rising:
            reasons.append("rising: corroboration accelerating, mainstream press still thin")
        if authority:
            reasons.append("primary/official source present")
        if not prior:
            reasons.append("novel: not seen in recent cycles")

        out.append(TrendScore(event_id=ev.id, score=round(score, 4),
                              velocity=round(velocity, 3), novelty=round(novelty, 3),
                              rising_before_mainstream=rising, reasons=reasons))

        topics[key] = {"count": max(cur, prior_count), "ts": now}

    state["topics"] = topics
    _save_state(state_path, state)
    out.sort(key=lambda t: (t.rising_before_mainstream, t.score), reverse=True)
    return out
