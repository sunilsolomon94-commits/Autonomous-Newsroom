"""Compile the daily email brief from the day's gated stories.

Two tiers from the same gated stories:
  free : skimmable, sourced headlines + one line each.
  ext  : adds an analysis layer ("what it means"), the early-signal section from the
         trend radar, and the searchable archive.

The assembly here is deterministic (no credentials): it structures the brief from
the day's multi-outlet stories + the trend radar's early signals, and renders it to
Markdown and branded HTML. The "what it means" analysis prose for the extended tier is
the one credentialed step. Nothing here asserts a claim as verified unless the editorial
gate (pipeline/verify.py) already passed it -- the free brief is sourced headline
aggregation ("here is what multiple outlets are reporting, with links"); verified claims
get the fuller treatment downstream.

Story dict shape (what the orchestrator passes in):
  {"headline": str,
   "sources": [{"publisher": str, "url": str, "tier": int}, ...],
   "decision": "publish" | "hold" | None}     # None when run with no API key
"""
from __future__ import annotations
import os
import re
import datetime as dt
import html as _html

# Deterministic AI-relevance filter -- keeps the brief on-topic (AI/tech) and drops the
# space/gaming/general-news that the general tech feeds also carry. No model call.
# Single tokens are matched as WHOLE WORDS (so "ai" does not match "available"); phrases
# are matched as substrings.
_AI_WORDS = {
    "ai", "agi", "llm", "llms", "gpt", "chatgpt", "openai", "anthropic", "claude",
    "gemini", "deepmind", "llama", "mistral", "huggingface", "nvidia", "gpu", "tpu",
    "neural", "chatbot", "agentic", "transformer", "transformers", "diffusion",
    "multimodal", "copilot", "codex", "quantization", "quantisation", "arxiv",
    "generative", "embedding", "embeddings", "rag", "inference", "model", "models",
    "dataset", "datasets", "benchmark", "benchmarks", "prompt", "prompts",
}
_AI_PHRASES = {
    "artificial intelligence", "machine learning", "deep learning", "neural network",
    "language model", "foundation model", "hugging face", "fine-tun", "open-source model",
    "open source model", "data center", "data centre", "self-driving", "computer vision",
    "speech recognition",
}


def is_ai_relevant(text: str) -> bool:
    """True if the text is AI/tech on-topic. Whole-word match for single tokens,
    substring match for multi-word phrases."""
    t = (text or "").lower()
    if any(p in t for p in _AI_PHRASES):
        return True
    return bool(set(re.findall(r"[a-z0-9]+", t)) & _AI_WORDS)


# Tidy RSS feed-title noise into clean outlet names for the reader-facing brief.
_PUB_MAP = {
    "www.theregister.com - articles": "The Register",
    "engadget - technology news & expert reviews": "Engadget",
    "ai | venturebeat": "VentureBeat",
    "ai": "Google AI Blog",
    "localllama": "r/LocalLLaMA",
    "machine learning": "r/MachineLearning",
    "openai news": "OpenAI",
    "mit technology review": "MIT Technology Review",
}


def _pub_name(src: dict) -> str:
    """Clean display name for an outlet from its (often noisy) RSS feed title."""
    raw = (src.get("publisher") or "").strip()
    mapped = _PUB_MAP.get(raw.lower())
    if mapped:
        return mapped
    p = re.sub(r"\s*[-–|:]\s*(articles|technology news.*|latest.*|rss.*|feed.*)$",
               "", raw, flags=re.I)
    p = re.sub(r"^www\.", "", p)
    return p or "source"


def _distinct_by_publisher(sources: list[dict]) -> list[dict]:
    """One entry per distinct (cleaned) outlet name, first URL kept, order-preserving --
    mirrors the outlet-independence rule so the display shows distinct outlets, not the
    same one twice."""
    seen, out = set(), []
    for src in sources:
        name = _pub_name(src)
        if name in seen:
            continue
        seen.add(name)
        out.append(src)
    return out


def _verified(story: dict) -> bool:
    return story.get("decision") == "publish"


def social_post(stories: list[dict], persona: dict | None = None,
                signup_url: str = "") -> str:
    """A short, ToS-clean text post from the top story -- the daily reach hook.
    No hype, no editorializing; the format IS the brand (sourced + a link)."""
    name = (persona or {}).get("channel", {}).get("name", "Cited")
    today = dt.date.today().isoformat()
    if not stories:
        body = ("Quiet day in AI -- nothing cleared two independent outlets yet. "
                "We hold when sources are thin. That's the point.")
        tail = f"\n\n{signup_url}".rstrip()
        return f"{name} - {today}\n\n{body}{tail}\n\n#AI #AInews"
    s = stories[0]
    pubs = [_pub_name(src) for src in _distinct_by_publisher(s.get("sources", []))]
    pub_line = " + ".join(pubs[:3]) if pubs else "multiple outlets"
    mark = "  [verified by Cited's gate]" if _verified(s) else ""
    lines = [
        f"{name} - {today}",
        "",
        s.get("headline", "").strip(),
        "",
        f"Reported by {pub_line}.{mark}",
        "Every claim sourced. Code + audit log are public.",
    ]
    if signup_url:
        lines += ["", signup_url]
    lines += ["", "#AI #AInews"]
    return "\n".join(lines)


def compile_brief(stories: list[dict], early_signals: list[dict] | None = None,
                  tier: str = "free", signup_url: str = "") -> str:
    """Build the brief body as Markdown. tier in {'free','pro'}. Pro analysis needs a key."""
    early_signals = early_signals or []
    today = dt.date.today().isoformat()
    lines = [f"# Cited - {today}",
             "AI newsroom. Every claim sourced. All code open.", ""]

    if stories:
        lines.append("## What multiple outlets are reporting today")
        for s in stories:
            head = (s.get("headline") or "(untitled)").strip()
            chips = " · ".join(
                f"[{_pub_name(src)}]({src.get('url', '')})" if src.get("url")
                else _pub_name(src)
                for src in _distinct_by_publisher(s.get("sources", [])))
            mark = "  ✓ verified by Cited's gate" if _verified(s) else ""
            lines.append(f"- **{head}**{mark}")
            if chips:
                lines.append(f"  Sources: {chips}")
    else:
        lines.append("## A quiet cycle")
        lines.append("Nothing cleared two independent outlets this cycle. Cited holds "
                     "when sourcing is thin -- that restraint is the product.")

    if tier == "ext":
        rising = [sig for sig in early_signals if sig.get("rising_before_mainstream")]
        if rising:
            lines += ["", "## Early signals (rising before mainstream)"]
            for sig in rising:
                lines.append(f"- topic {sig['id']} (velocity {sig.get('velocity')})")
        lines += ["", "## What it means"]
        if not os.environ.get("ANTHROPIC_API_KEY"):
            lines.append("_[analysis layer is credentialed - wire the model call]_")
        else:
            # BUILD: model writes the sourced 'what it means' analysis per story.
            lines.append("_[generated analysis goes here]_")

    lines += ["", "---",
              "Why you can trust this: every item shows its sources. The code and the "
              "tamper-evident audit log are public. Verify me, not trust me."]
    if signup_url:
        lines.append(f"Get the brief daily: {signup_url}")
    return "\n".join(lines)


def render_html(stories: list[dict], early_signals: list[dict] | None = None,
                persona: dict | None = None, tier: str = "free",
                signup_url: str = "") -> str:
    """Render the brief to branded, email-safe HTML (inline styles, brand palette)."""
    early_signals = early_signals or []
    brand = (persona or {}).get("brand", {})
    pal = brand.get("palette", {})
    ink = pal.get("ink", "#15171C")
    paper = pal.get("paper", "#F4F1EA")
    accent = pal.get("accent", "#3FB8C4")
    cite = pal.get("cite", "#E0A23C")
    today = dt.date.today().isoformat()
    esc = _html.escape

    def chip(src):
        pub = esc(_pub_name(src))
        url = src.get("url", "")
        style = (f"display:inline-block;margin:2px 6px 2px 0;padding:2px 9px;"
                 f"border:1px solid {accent};border-radius:11px;color:{ink};"
                 f"font-size:12px;text-decoration:none;")
        return f'<a href="{esc(url)}" style="{style}">{pub}</a>' if url else \
               f'<span style="{style}">{pub}</span>'

    items = []
    for s in stories:
        head = esc((s.get("headline") or "(untitled)").strip())
        chips = "".join(chip(src) for src in _distinct_by_publisher(s.get("sources", [])))
        badge = (f'<span style="color:{accent};font-weight:600;font-size:12px;">'
                 f'&#10003; verified by Cited&#39;s gate</span>') if _verified(s) else ""
        items.append(
            f'<li style="margin:0 0 16px;list-style:none;">'
            f'<div style="font-weight:700;font-size:16px;line-height:1.35;">{head}</div>'
            f'<div style="margin-top:5px;">{chips}</div>'
            f'<div style="margin-top:3px;">{badge}</div></li>')
    if not items:
        items = ['<li style="list-style:none;color:#555;">A quiet cycle - nothing '
                 'cleared two independent outlets. Cited holds when sourcing is thin.</li>']

    pro_html = ""
    if tier == "ext":
        rising = [s for s in early_signals if s.get("rising_before_mainstream")]
        sig_html = "".join(
            f'<li>topic {esc(str(s["id"]))} (velocity {esc(str(s.get("velocity")))})</li>'
            for s in rising)
        if sig_html:
            pro_html = (f'<h2 style="color:{ink};font-size:15px;">Early signals '
                        f'(rising before mainstream)</h2><ul>{sig_html}</ul>')

    cta = (f'<a href="{esc(signup_url)}" style="color:{ink};background:{cite};'
           f'padding:9px 16px;border-radius:6px;text-decoration:none;font-weight:600;">'
           f'Get the brief daily</a>') if signup_url else ""

    # A thin verification ring (the brand motif), inline SVG.
    ring = (f'<svg width="22" height="22" viewBox="0 0 22 22" style="vertical-align:middle">'
            f'<circle cx="11" cy="11" r="8" fill="none" stroke="{accent}" stroke-width="2"/>'
            f'<path d="M7 11 l3 3 l5 -6" fill="none" stroke="{cite}" stroke-width="2"/></svg>')

    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:{paper};color:{ink};
font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:28px 22px;">
  <div style="border-bottom:2px solid {ink};padding-bottom:10px;margin-bottom:18px;">
    {ring} <span style="font-weight:800;font-size:20px;letter-spacing:0.5px;">Cited</span>
    <div style="font-size:12px;color:#555;margin-top:2px;">
      AI newsroom. Every claim sourced. All code open. &middot; {today}</div>
  </div>
  <h2 style="color:{ink};font-size:15px;margin:0 0 12px;">What multiple outlets are reporting today</h2>
  <ul style="padding:0;margin:0;">{''.join(items)}</ul>
  {pro_html}
  <div style="margin-top:24px;padding-top:14px;border-top:1px solid #ccc;font-size:13px;color:#444;">
    Why you can trust this: every item shows its sources. The code and the
    tamper-evident audit log are public. <b>Verify me, not trust me.</b>
  </div>
  <div style="margin-top:18px;">{cta}</div>
</div></body></html>"""
