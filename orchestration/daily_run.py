"""End to end daily run. AI builds, AI runs.

Selects the day's top story by score, extracts and grounds its claims, gates it,
and publishes only if it passes. Steps marked [CREDENTIALED] need the operator's
keys and are wired in the operator's environment.

Run from repo root:
    PYTHONPATH=. python orchestration/daily_run.py            # full run
    PYTHONPATH=. python orchestration/daily_run.py --dry-run  # skip render+publish
"""
import os
import sys
import json
import yaml
from pipeline import ingest, cluster, verify, script, audit, render, clips, publish

RULES = yaml.safe_load(open("config/editorial_rules.yaml"))
PERSONA = yaml.safe_load(open("config/persona.yaml"))
AUDIT_LOG = "data/audit_log.jsonl"
MAX_CANDIDATES = 10   # bound daily LLM cost: only evaluate the top-scored events


def _score(ev) -> float:
    n = len({i["id"] for i in ev.items})
    has_t1 = any(i.get("tier") == 1 for i in ev.items)
    return 0.35 * n + (0.3 if has_t1 else 0.0)   # add recency/novelty/intent weights to tune


def _already_published(path) -> set:
    if not os.path.exists(path):
        return set()
    ids = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and json.loads(line).get("decision") == "publish":
                ids.add(json.loads(line)["story_id"])
    return ids


def run(dry_run: bool = False):
    raw = ingest.fetch_all("config/sources.yaml")           # [CREDENTIALED]
    events = cluster.group(raw)
    seen = _already_published(AUDIT_LOG)
    candidates = sorted((e for e in events if e.id not in seen),
                        key=_score, reverse=True)[:MAX_CANDIDATES]

    selected = None
    for ev in candidates:
        claims = cluster.to_claims(ev)                      # [CREDENTIALED]
        claims = cluster.verify_grounding(ev, claims)       # [CREDENTIALED] grounding pass
        gate = verify.evaluate_story(claims, RULES)
        audit.append(AUDIT_LOG, ev.id, gate.decision, gate.reasons,
                     [s["id"] for s in ev.sources])
        if gate.decision == "publish":
            selected = (ev, claims)
            break

    if not selected:
        return []                                           # nothing passed; holds are logged

    ev, claims = selected
    text = script.write(ev, claims, PERSONA)                # [CREDENTIALED]
    if dry_run:
        print("[dry-run] would publish:", ev.id)
        print(text)
        return [ev.id]
    video = render.to_video(text, PERSONA)                  # [CREDENTIALED]
    shorts = clips.cut(video, PERSONA)
    publish.send(video, shorts, PERSONA)                    # [CREDENTIALED]
    return [ev.id]


if __name__ == "__main__":
    print("published:", run(dry_run="--dry-run" in sys.argv))
