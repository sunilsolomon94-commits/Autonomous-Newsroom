"""The hands-off daily loop. Runs unattended after the one-time setup (see SETUP.md).

  radar -> cluster -> trend-rank -> extract -> ground -> gate -> audit -> draft

With no ANTHROPIC_API_KEY it runs the free half (ingest, cluster, radar) and prints
the ranked early-signal slate it WOULD draft. With a key it runs the editorial loop
end to end and saves the day's draft anchor script to data/draft_script.txt.

Kill switch: a file named HALT in the repo root exits cleanly before any work.
NAMED-PERSON SAFETY RULE: any negative/contested claim about an identifiable
living person is dropped in code, regardless of sourcing.
"""
from __future__ import annotations
import os
import sys
import json
import datetime as dt
import yaml

from pipeline import ingest, cluster, verify, audit, trends, script

RULES = yaml.safe_load(open("config/editorial_rules.yaml"))
PERSONA = yaml.safe_load(open("config/persona.yaml"))
AUDIT_LOG = "data/audit_log.jsonl"
TREND_STATE = "data/trend_state.json"
MAX_CANDIDATES = 6      # cost brake: at most this many events get model calls per run
SIGNUP_URL = os.environ.get("CITED_SIGNUP_URL", "")   # set once the signup page is live


def _halted() -> bool:
    return os.path.exists("HALT")


def _emit_brief(candidates, early_signals, decisions_by_id=None) -> dict:
    """Distribution: write the day's free brief (Markdown + branded HTML) and a
    short social post to data/. Deterministic, no credentials needed. Guarded so brief
    generation can never break the editorial run -- the gate is what matters."""
    try:
        from pipeline import newsletter
        decisions_by_id = decisions_by_id or {}
        stories = []
        for ev in candidates:
            head = ev.items[0].get("title", "") if ev.items else ""
            body = (ev.items[0].get("body") or "") if ev.items else ""
            if not newsletter.is_ai_relevant(head + " " + body):
                continue
            srcs = [{"publisher": s.get("publisher") or s["id"],
                     "url": s.get("url", ""), "tier": s.get("tier")} for s in ev.sources]
            stories.append({"headline": head, "sources": srcs,
                            "decision": decisions_by_id.get(ev.id)})
        os.makedirs("data", exist_ok=True)
        today = dt.date.today().isoformat()
        artifacts = {
            f"data/brief_{today}.md": newsletter.compile_brief(
                stories, early_signals, tier="free", signup_url=SIGNUP_URL),
            f"data/brief_{today}.html": newsletter.render_html(
                stories, early_signals, PERSONA, tier="free", signup_url=SIGNUP_URL),
            f"data/post_{today}.txt": newsletter.social_post(
                stories, PERSONA, signup_url=SIGNUP_URL),
        }
        for path, content in artifacts.items():
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        print(f"Brief written: data/brief_{today}.md (+.html), data/post_{today}.txt "
              f"[{len(stories)} AI-relevant stories]")
        return {"brief_stories": len(stories), "brief_path": f"data/brief_{today}.md"}
    except Exception as e:
        print(f"[brief] skipped (non-fatal): {str(e)[:160]}")
        return {}


def _already_published(path: str) -> set:
    if not os.path.exists(path):
        return set()
    ids = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and json.loads(line).get("decision") == "publish":
                ids.add(json.loads(line)["story_id"])
    return ids


def _distinct_publishers(ev) -> int:
    return len({(it.get("publisher") or it["id"]) for it in ev.items})


def run(dry_run: bool = True) -> dict:
    if _halted():
        print("HALT present -- exiting cleanly.")
        return {"halted": True}

    raw = ingest.fetch_all("config/sources.yaml")
    events = cluster.group(raw)
    ranked = trends.score_events(events, TREND_STATE)
    seen = _already_published(AUDIT_LOG)
    by_id = {e.id: e for e in events}
    candidates = [by_id[t.event_id] for t in ranked
                  if t.event_id not in seen
                  and _distinct_publishers(by_id[t.event_id]) >= 2][:MAX_CANDIDATES]

    report = {
        "ts": dt.datetime.utcnow().isoformat(),
        "ingested": len(raw),
        "events": len(events),
        "early_signals": [
            {"id": t.event_id, "score": t.score, "velocity": t.velocity,
             "rising_before_mainstream": t.rising_before_mainstream}
            for t in ranked[:5]
        ],
        "multi_outlet_candidates": len(candidates),
    }

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[no ANTHROPIC_API_KEY] radar ran (free half). Would extract + gate + draft:")
        report.update(_emit_brief(candidates, report["early_signals"]))
        print(json.dumps(report, indent=2))
        return report

    if not candidates:
        print("No multi-outlet stories this cycle -- model spend skipped, radar state updated.")
        report.update(_emit_brief(candidates, report["early_signals"]))
        print(json.dumps(report, indent=2))
        return report

    decisions = []
    selected = None
    for ev in candidates:
        try:
            claims = cluster.to_claims(ev)
            claims = cluster.verify_grounding(ev, claims)
        except Exception as e:
            decisions.append({"id": ev.id, "decision": "error", "error": str(e)[:200]})
            continue
        # NAMED-PERSON SAFETY RULE: never carry a negative claim about a living person.
        claims = [c for c in claims
                  if not (c.names_living_person and c.negative_about_person)]
        gate = verify.evaluate_story(claims, RULES)
        audit.append(AUDIT_LOG, ev.id, gate.decision, gate.reasons,
                     [s["id"] for s in ev.sources])
        decisions.append({"id": ev.id, "decision": gate.decision,
                          "claims": len(claims), "reasons": gate.reasons[:3]})
        if gate.decision == "publish" and selected is None:
            selected = (ev, claims)

    report["decisions"] = decisions

    decisions_by_id = {d["id"]: d.get("decision") for d in decisions}
    report.update(_emit_brief(candidates, report["early_signals"], decisions_by_id))

    if selected:
        ev, claims = selected
        text = script.write(ev, claims, PERSONA)
        os.makedirs("data", exist_ok=True)
        with open("data/draft_script.txt", "w") as f:
            f.write(f"# Draft anchor script -- story {ev.id}\n"
                    f"# Topic: {ev.items[0].get('title', '')}\n\n{text}\n")
        report["selected"] = ev.id
        report["draft_preview"] = text[:400]
        print("DRAFTED:", ev.items[0].get("title", "")[:80])
    else:
        print("No story passed the gates this run. Holds are logged. Holding is safe.")

    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
