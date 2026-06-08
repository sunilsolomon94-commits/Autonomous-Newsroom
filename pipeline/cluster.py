"""Cluster raw items into events, then extract and ground claims with the model.

group() is pure logic. to_claims() and verify_grounding() are credentialed.
v1.1: claim independence is counted by distinct PUBLISHER (outlet), not by
article -- two posts from the same outlet are one voice, not two.
v1.2: cross-outlet corroboration is treated as the key signal. to_claims now
attributes a fact to ALL outlets that support it in substance (not just the one
whose phrasing was used); verify_grounding is a combined grounding + corroboration
pass that, for each kept claim, also pulls in any OTHER event sources that support
it -- recovering real cross-outlet corroboration the extractor under-credited.
Clustering is tightened: same min_overlap, but an event also needs >=1 shared
entity-like (capitalized) token, so related-but-different stories no longer glue.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass

from pipeline.verify import Claim

_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "with",
         "at", "by", "is", "are", "as", "new", "its", "it", "this", "that"}

# Capitalized headline words that carry no story identity -- they would otherwise
# count as a shared "entity" and re-introduce the loose-cluster glue.
_FUNC = {"how", "what", "why", "when", "where", "who", "which", "take", "see",
         "here", "there", "your", "our", "their", "can", "will", "get", "make",
         "does", "meet", "watch", "look", "best", "top"}


@dataclass
class Event:
    id: str
    items: list[dict]

    @property
    def sources(self) -> list[dict]:
        out, seen = [], set()
        for it in self.items:
            if it["id"] in seen:
                continue
            seen.add(it["id"])
            out.append({"id": it["id"], "url": it.get("url", ""),
                        "tier": it.get("tier"), "publisher": it.get("publisher")})
        return out


def _tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return {w for w in words if w not in _STOP and len(w) > 2}


def _entity_tokens(title: str) -> set[str]:
    """Entity-like tokens: capitalized words / ALL-CAPS acronyms (len>2),
    lowercased for matching, minus stopwords and common headline function-words.
    A shared one of these (a company/model/product name like OpenAI, KVarN, AWS)
    is the 'same story' signal that bare token overlap lacks."""
    words = re.findall(r"[A-Za-z0-9]+", title or "")
    ents = set()
    for w in words:
        lw = w.lower()
        if len(w) <= 2 or lw in _STOP or lw in _FUNC:
            continue
        if w[0].isupper():
            ents.add(lw)
    return ents


def group(raw: list[dict], min_overlap: int = 2, require_entity: bool = True) -> list[Event]:
    """Bucket items whose titles share >= min_overlap significant tokens AND
    (v1.2) at least one entity-like token. The entity requirement keeps
    related-but-different stories ("How we used Gemini" vs "How Wasmer used
    Codex") from gluing into one event just because they share generic verbs."""
    buckets: list[list] = []   # [content_tokens, items, entity_tokens]
    for it in raw:
        toks = _tokens(it.get("title", ""))
        ents = _entity_tokens(it.get("title", ""))
        placed = False
        for b in buckets:
            if len(toks & b[0]) >= min_overlap and (not require_entity or len(ents & b[2]) >= 1):
                b[1].append(it)
                b[0] |= toks
                b[2] |= ents
                placed = True
                break
        if not placed:
            buckets.append([set(toks), [it], set(ents)])
    return [Event(id=items[0]["id"], items=items) for _, items, _ in buckets]


def _dedupe_by_publisher(ids: list[str], pub_by_id: dict) -> list[str]:
    """v1.1 INDEPENDENCE RULE: one voice per outlet. Keep a single source per
    distinct publisher so the gate counts genuinely independent corroboration,
    never the same outlet twice. Order-preserving."""
    seen_pubs, indep = set(), []
    for s in ids:
        p = pub_by_id.get(s, s)
        if p in seen_pubs:
            continue
        seen_pubs.add(p)
        indep.append(s)
    return indep


def _source_digest(ev: Event, body_chars: int = 1500, max_items: int = 6) -> str:
    parts = []
    for it in ev.items[:max_items]:
        parts.append(f"[{it['id']} | tier {it.get('tier')} | {it.get('publisher', '')}]\n"
                     f"TITLE: {it.get('title', '')}\nBODY: {(it.get('body') or '')[:body_chars]}")
    return "\n---\n".join(parts)


def to_claims(ev: Event) -> list[Claim]:
    """Editorial agent: extract cited claims from the event's actual source text."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set: editorial extraction is credentialed")
    from pipeline import llm
    system = open("prompts/editorial_system.md").read()
    user = (
        "SOURCES (the only ground truth; do not use outside knowledge):\n\n"
        + _source_digest(ev) +
        "\n\nExtract at most 5 factual claims these sources support. Return ONLY a JSON array:"
        ' [{"text": str, "source_ids": [str], "names_living_person": bool,'
        ' "negative_about_person": bool, "subject_response_present": bool}]'
        "\nCROSS-OUTLET CORROBORATION (key signal): if multiple sources report the"
        " same fact in different words, attribute the claim to ALL source_ids that"
        " support it in substance -- not only the source whose wording you used."
        " Two outlets saying the same thing, however phrased, are two sources."
        "\nPhase rule: drop entirely any negative or contested claim about an"
        " identifiable living person.")
    raw = llm.parse_json(llm.complete(system, user, model=llm.HAIKU, max_tokens=1200))
    tier_by_id = {it["id"]: it.get("tier", 3) for it in ev.items}
    pub_by_id = {it["id"]: (it.get("publisher") or it["id"]) for it in ev.items}
    claims: list[Claim] = []
    for c in raw if isinstance(raw, list) else []:
        ids = [s for s in c.get("source_ids", []) if s in tier_by_id]
        ids = _dedupe_by_publisher(ids, pub_by_id)
        if not c.get("text") or not ids:
            continue
        claims.append(Claim(
            text=c["text"], source_ids=ids, tiers=[tier_by_id[s] for s in ids],
            names_living_person=bool(c.get("names_living_person")),
            negative_about_person=bool(c.get("negative_about_person")),
            subject_response_present=bool(c.get("subject_response_present"))))
    return claims[:5]


def verify_grounding(ev: Event, claims: list[Claim]) -> list[Claim]:
    """Combined grounding + corroboration pass (one model call).

    For each claim the checker decides (1) keep: does the cited source text
    clearly support it in substance (if unsure, fail); and (2) corroboration:
    which OTHER sources in the event support the same fact in substance, however
    worded. Corroborating source_ids are merged in and re-deduped by publisher,
    so genuine cross-outlet support the extractor missed reaches the gate."""
    if not claims:
        return []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set: grounding pass is credentialed")
    from pipeline import llm
    tier_by_id = {it["id"]: it.get("tier", 3) for it in ev.items}
    pub_by_id = {it["id"]: (it.get("publisher") or it["id"]) for it in ev.items}
    listing = "\n".join(f'{i}. "{c.text}" (cites: {", ".join(c.source_ids)})'
                        for i, c in enumerate(claims))
    system = ("You are a strict grounding and corroboration checker. For each claim: "
              "(1) GROUNDED -- it passes only if the cited source text clearly supports "
              "it, in substance; if unsure, fail it. (2) CORROBORATION -- if kept, list "
              "every source_id in SOURCES that supports the same fact in substance, "
              "even in different words, INCLUDING sources not originally cited. "
              "Cross-outlet corroboration is the key signal; do not under-report it.")
    user = ("SOURCES:\n\n" + _source_digest(ev) +
            "\n\nCLAIMS:\n" + listing +
            '\n\nReturn ONLY JSON: [{"i": int, "keep": bool, "corroborating_source_ids": [str]}]'
            "\ncorroborating_source_ids must use the bracketed source ids above and may be"
            " empty; list ALL sources that support the claim in substance.")
    raw = llm.parse_json(llm.complete(system, user, model=llm.HAIKU, max_tokens=600))
    by_i = {r["i"]: r for r in raw if isinstance(r, dict)}
    kept: list[Claim] = []
    for i, c in enumerate(claims):
        r = by_i.get(i)
        if not r or not r.get("keep"):
            continue
        merged = list(c.source_ids)
        for s in r.get("corroborating_source_ids", []):
            if s in tier_by_id and s not in merged:
                merged.append(s)
        ids = _dedupe_by_publisher(merged, pub_by_id)
        c.source_ids = ids
        c.tiers = [tier_by_id[s] for s in ids]
        kept.append(c)
    return kept
