"""Deterministic editorial gates. The non-negotiable, no-human-override layer.

This module is the heart of "every claim cited or it does not ship." It is pure
logic: no network, no credentials, no model calls. The editorial agent (cluster.py)
proposes claims; this module decides publish vs. hold against
config/editorial_rules.yaml.

Source authority tiers:
  tier 1 = primary / official (company blog, research paper, regulator filing)
  tier 2 = reputable independent press
  tier 3 = aggregators (GDELT, HN frontpage) -- never satisfy authority alone

A claim clears, in order:
  1. independent-source count        >= min_independent_sources
  2. authority                       one tier-1 OR >= require_tier1_or_tier2_count tier-2
  3. named-person gate (if triggered) stricter bar; hard hold on failure
  4. no unresolved source conflict
  5. aggregate confidence            >= publish_threshold
A story holds if ANY of its claims holds. Holding is always safe.

The contract is fixed by config/editorial_rules.yaml and the five cases in
tests/smoke.py, plus prompts/editorial_system.md. Behaviour on all five smoke
cases is verified; run tests/smoke.py to confirm.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Claim:
    text: str
    source_ids: list[str]
    tiers: list[int]
    names_living_person: bool = False
    negative_about_person: bool = False
    subject_response_present: bool = False
    conflicts: bool = False


@dataclass
class GateResult:
    decision: str                                   # "publish" | "hold"
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0


def _independent_sources(claim: Claim) -> int:
    return len(set(claim.source_ids))


def _has_tier1(claim: Claim) -> bool:
    return any(t == 1 for t in claim.tiers)


def _independent_tier2(claim: Claim) -> int:
    seen = set()
    for sid, t in zip(claim.source_ids, claim.tiers):
        if t == 2:
            seen.add(sid)
    return len(seen)


def evaluate_claim(claim: Claim, rules: dict) -> tuple[bool, list[str], float]:
    cg = rules["confidence_gate"]
    npg = rules.get("named_person_gate", {})
    reasons: list[str] = []
    score = 0.0

    n = _independent_sources(claim)
    sources_ok = n >= cg["min_independent_sources"]
    if sources_ok:
        score += 0.4
    else:
        reasons.append(f"only {n} independent source(s); need {cg['min_independent_sources']}")

    has_t1 = _has_tier1(claim)
    t2 = _independent_tier2(claim)
    authority_ok = has_t1 or t2 >= cg["require_tier1_or_tier2_count"]
    if authority_ok:
        score += 0.4
    else:
        reasons.append(
            f"authority not met: no tier-1 and only {t2} tier-2 source(s) "
            f"(need 1 tier-1 or {cg['require_tier1_or_tier2_count']} tier-2)")

    # Named-person gate: hard hold on failure, independent of score.
    named_ok = True
    triggered = bool(npg.get("enabled") and claim.names_living_person and claim.negative_about_person)
    if triggered:
        if n < npg["required_independent_sources"]:
            named_ok = False
            reasons.append(
                f"named-person gate: {n} source(s); need {npg['required_independent_sources']}")
        if npg.get("require_tier1_source") and not has_t1:
            named_ok = False
            reasons.append("named-person gate: a tier-1 source is required")
        if npg.get("require_subject_response_or_note") and not claim.subject_response_present:
            named_ok = False
            reasons.append("named-person gate: subject response (or noted absence) is required")
    if named_ok:
        score += 0.2

    conflict_ok = not (cg.get("hold_if_sources_conflict") and claim.conflicts)
    if not conflict_ok:
        reasons.append("sources conflict on a factual point")

    passes = (sources_ok and authority_ok and named_ok and conflict_ok
              and score >= cg["publish_threshold"])
    return passes, reasons, score


def evaluate_story(claims: list[Claim], rules: dict) -> GateResult:
    all_reasons: list[str] = []
    scores: list[float] = []
    decision = "publish"
    for c in claims:
        ok, reasons, score = evaluate_claim(c, rules)
        scores.append(score)
        all_reasons.extend(reasons)
        if not ok:
            decision = "hold"
    if not claims:
        return GateResult(decision="hold", reasons=["no claims extracted"], confidence=0.0)
    return GateResult(decision=decision, reasons=all_reasons, confidence=min(scores))
