"""Build the public website for Cited -- the live, autonomous newsroom in the open.

Reads what the daily run already produced in data/ (the dated briefs and the
hash-chained audit log) and renders a static site/ folder:

  site/index.html      today's brief + the audit-log proof + signup CTA
  site/audit.html      the full, verifiable audit log (the "verify me" centrepiece)
  site/archive.html    every past brief, by date
  site/briefs/*.html   the dated brief pages (copied from data/)

Pure logic: no credentials, stdlib + pyyaml only. Deterministic and idempotent --
safe to run every cycle. The audit log is the core: this is what makes "verify me,
not trust me" a thing a stranger can actually check.

Run:  PYTHONPATH=. python pipeline/site.py
"""
from __future__ import annotations
import glob
import html as _html
import json
import os
import re
import shutil
import datetime as dt

import yaml

from pipeline import audit

REPO_URL = "https://github.com/sunilsolomon94-commits/Autonomous-Newsroom"
DATA = "data"
OUT = "site"
AUDIT_LOG = os.path.join(DATA, "audit_log.jsonl")


def _palette() -> dict:
    try:
        p = yaml.safe_load(open("config/persona.yaml"))
        return p.get("brand", {}).get("palette", {})
    except Exception:
        return {}


def _chrome(title: str, body: str, pal: dict, active: str = "") -> str:
    ink = pal.get("ink", "#15171C")
    paper = pal.get("paper", "#F4F1EA")
    accent = pal.get("accent", "#3FB8C4")
    cite = pal.get("cite", "#E0A23C")
    esc = _html.escape

    def nav(href, label, key):
        weight = "700" if key == active else "400"
        return (f'<a href="{href}" style="color:{ink};text-decoration:none;'
                f'font-weight:{weight};margin-right:18px;">{esc(label)}</a>')

    ring = (f'<svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">'
            f'<circle cx="15" cy="15" r="11" fill="none" stroke="{accent}" stroke-width="2.4"/>'
            f'<path d="M9.5 15 l3.5 3.5 l7 -8" fill="none" stroke="{cite}" stroke-width="2.4" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="Cited - an autonomous, open-source AI newsroom. Every claim sourced, every decision in a public tamper-evident audit log. Verify me, not trust me.">
</head>
<body style="margin:0;background:{paper};color:{ink};
font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.55;">
<div style="max-width:760px;margin:0 auto;padding:30px 22px 56px;">
  <header style="display:flex;align-items:center;gap:11px;border-bottom:2px solid {ink};padding-bottom:12px;">
    {ring}
    <div style="flex:1;">
      <div style="font-weight:800;font-size:22px;letter-spacing:.5px;">Cited</div>
      <div style="font-size:12px;color:#555;">AI newsroom. Every claim sourced. All code open.</div>
    </div>
  </header>
  <nav style="margin:16px 0 26px;font-size:14px;">
    {nav('index.html','Today','today')}{nav('audit.html','Audit log','audit')}
    {nav('archive.html','Archive','archive')}{nav('subscribe.html','Get the brief','subscribe')}
    <a href="{REPO_URL}" style="color:{ink};margin-right:0;">Source code</a>
  </nav>
  {body}
  <footer style="margin-top:42px;padding-top:16px;border-top:1px solid #ccc;font-size:12px;color:#666;">
    Autonomous &amp; open-source. The machine decides coverage; every decision is logged to a
    public, tamper-evident chain. <b>Verify me, not trust me.</b><br>
    <a href="{REPO_URL}" style="color:#666;">{esc(REPO_URL)}</a>
  </footer>
</div></body></html>"""


def _latest_brief_md() -> tuple[str, str] | None:
    files = sorted(glob.glob(os.path.join(DATA, "brief_*.md")))
    if not files:
        return None
    path = files[-1]
    date = re.search(r"brief_(\d{4}-\d{2}-\d{2})\.md", os.path.basename(path))
    return path, (date.group(1) if date else "")


def _headlines_from_md(md_path: str) -> list[tuple[str, str]]:
    """Pull (headline, sources_line) pairs from a brief markdown file."""
    out, pending = [], None
    for line in open(md_path, encoding="utf-8"):
        m = re.match(r"- \*\*(.+?)\*\*(.*)$", line.strip())
        if m:
            pending = (m.group(1).strip() + (" " + m.group(2).strip() if m.group(2).strip() else ""))
            out.append([pending, ""])
        elif line.strip().startswith("Sources:") and out:
            out[-1][1] = line.strip()[len("Sources:"):].strip()
    return [(h, s) for h, s in out]


def _read_audit() -> list[dict]:
    if not os.path.exists(AUDIT_LOG):
        return []
    entries = []
    for line in open(AUDIT_LOG, encoding="utf-8"):
        if line.strip():
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def _index_page(pal: dict) -> str:
    esc = _html.escape
    accent = pal.get("accent", "#3FB8C4")
    cite = pal.get("cite", "#E0A23C")
    latest = _latest_brief_md()
    parts = [
        '<h1 style="font-size:30px;line-height:1.2;margin:0 0 10px;">'
        'The AI brief that shows its receipts.</h1>',
        '<p style="font-size:17px;color:#333;margin:0 0 28px;">'
        'An autonomous, open-source newsroom. A machine decides what matters in AI, '
        'attributes every claim to its sources, and logs every publish/hold decision to a '
        'public, tamper-evident chain you can check yourself.</p>',
    ]
    if latest:
        md_path, date = latest
        heads = _headlines_from_md(md_path)
        def md_links(text: str) -> str:
            # [label](url) -> <a>, with everything escaped; plain runs escaped too.
            out, pos = [], 0
            for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
                out.append(esc(text[pos:m.start()]))
                out.append(f'<a href="{esc(m.group(2), quote=True)}" '
                           f'style="color:#555;">{esc(m.group(1))}</a>')
                pos = m.end()
            out.append(esc(text[pos:]))
            return "".join(out)

        parts.append(f'<h2 style="font-size:16px;">Today &middot; {esc(date)}</h2><ul style="padding-left:18px;">')
        if heads:
            for h, s in heads:
                verified = "verified by Cited" in h
                h_clean = re.sub(r"\s*✓?\s*verified by Cited's gate", "", h).strip()
                head_html = esc(h_clean)
                if verified:
                    head_html += (f' <span style="color:{accent};font-weight:600;">'
                                  f'&#10003; verified</span>')
                src = f'<div style="font-size:12px;color:#555;">{md_links(s)}</div>' if s else ""
                parts.append(f'<li style="margin-bottom:10px;">{head_html}{src}</li>')
        else:
            parts.append('<li>A quiet cycle &mdash; nothing cleared two independent outlets. '
                         'Cited holds when sourcing is thin; that restraint is the product.</li>')
        parts.append('</ul>')
        bn = os.path.basename(md_path).replace(".md", ".html")
        if os.path.exists(os.path.join(OUT, "briefs", bn)):
            parts.append(f'<p><a href="briefs/{esc(bn)}" style="color:{cite};font-weight:600;">'
                         'Read the full brief &rarr;</a></p>')
    else:
        parts.append('<p>The first brief publishes on the next run.</p>')

    entries = _read_audit()
    intact = audit.verify_chain(AUDIT_LOG) if entries else True
    pub = sum(1 for e in entries if e.get("decision") == "publish")
    held = sum(1 for e in entries if e.get("decision") == "hold")
    badge = (f'<span style="color:{accent};">&#10003; chain intact</span>' if intact
             else '<span style="color:#b00;">&#10007; chain broken</span>')
    parts.append(
        f'<div style="margin-top:30px;padding:16px 18px;border:1px solid {accent};border-radius:10px;">'
        f'<div style="font-weight:700;">The audit log &mdash; the proof</div>'
        f'<div style="font-size:14px;color:#333;margin-top:6px;">'
        f'{len(entries)} decisions recorded &middot; {pub} published &middot; {held} held &middot; {badge}.'
        f' Every decision is hash-chained; tampering breaks the chain. '
        f'<a href="audit.html" style="color:{pal.get("ink","#15171C")};font-weight:600;">Inspect it &rarr;</a>'
        f'</div></div>')
    return "\n".join(parts)


def _audit_page(pal: dict) -> str:
    esc = _html.escape
    accent = pal.get("accent", "#3FB8C4")
    entries = _read_audit()
    intact = audit.verify_chain(AUDIT_LOG) if entries else True
    badge = (f'<span style="color:{accent};font-weight:700;">&#10003; chain intact</span>'
             if intact else '<span style="color:#b00;font-weight:700;">&#10007; chain broken</span>')
    rows = []
    for e in reversed(entries):                       # newest first
        reasons = "; ".join(e.get("reasons", []) or [])
        dec = e.get("decision", "")
        col = accent if dec == "publish" else "#9a7b00" if dec == "hold" else "#555"
        rows.append(
            f'<tr style="border-top:1px solid #ddd;vertical-align:top;">'
            f'<td style="padding:7px 8px;font-variant-numeric:tabular-nums;">{esc(str(e.get("seq","")))}</td>'
            f'<td style="padding:7px 8px;font-size:12px;color:#555;white-space:nowrap;">{esc(str(e.get("timestamp",""))[:19])}</td>'
            f'<td style="padding:7px 8px;color:{col};font-weight:600;">{esc(dec)}</td>'
            f'<td style="padding:7px 8px;font-size:13px;">{esc(reasons)}</td>'
            f'<td style="padding:7px 8px;font-size:12px;color:#777;">{len(e.get("sources",[]))}</td>'
            f'<td style="padding:7px 8px;font-family:monospace;font-size:11px;color:#999;">{esc(str(e.get("hash",""))[:12])}</td>'
            f'</tr>')
    if not rows:
        rows = ['<tr><td colspan="6" style="padding:12px;color:#777;">No decisions logged yet '
                '&mdash; the first publish from the next run will appear here.</td></tr>']
    body = (
        f'<h1 style="font-size:26px;margin:0 0 6px;">The audit log</h1>'
        f'<p style="color:#333;margin:0 0 8px;">Every editorial decision the machine makes, '
        f'append-only and hash-chained. Each entry includes the previous entry&#39;s hash, so any '
        f'silent edit breaks the chain. Status: {badge} ({len(entries)} entries).</p>'
        f'<p style="font-size:13px;color:#555;background:#fff;border-left:3px solid {accent};'
        f'padding:9px 12px;margin:0 0 18px;">Verify it yourself: '
        f'<code>git clone {REPO_URL}</code>, then '
        f'<code>PYTHONPATH=. python -c "from pipeline import audit; '
        f'print(audit.verify_chain(\'data/audit_log.jsonl\'))"</code>. It prints <code>True</code> '
        f'only if the chain is untampered.</p>'
        f'<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f'<thead><tr style="text-align:left;border-bottom:2px solid {pal.get("ink","#15171C")};">'
        f'<th style="padding:7px 8px;">#</th><th style="padding:7px 8px;">Time (UTC)</th>'
        f'<th style="padding:7px 8px;">Decision</th><th style="padding:7px 8px;">Reasons</th>'
        f'<th style="padding:7px 8px;">Srcs</th><th style="padding:7px 8px;">Hash</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>')
    return body


def _archive_page(pal: dict) -> str:
    esc = _html.escape
    cite = pal.get("cite", "#E0A23C")
    briefs = sorted(glob.glob(os.path.join(OUT, "briefs", "brief_*.html")), reverse=True)
    items = []
    for b in briefs:
        bn = os.path.basename(b)
        date = re.search(r"brief_(\d{4}-\d{2}-\d{2})\.html", bn)
        label = date.group(1) if date else bn
        items.append(f'<li style="margin-bottom:8px;">'
                     f'<a href="briefs/{esc(bn)}" style="color:{cite};font-weight:600;">{esc(label)}</a></li>')
    body = ['<h1 style="font-size:26px;margin:0 0 12px;">Archive</h1>']
    body.append('<ul style="padding-left:18px;">' + ("".join(items) or
                '<li>No briefs yet.</li>') + '</ul>')
    return "\n".join(body)


def build_site(out_dir: str = OUT) -> dict:
    pal = _palette()
    os.makedirs(out_dir, exist_ok=True)
    briefs_dir = os.path.join(out_dir, "briefs")
    os.makedirs(briefs_dir, exist_ok=True)

    # Copy the dated brief pages into the published site.
    copied = 0
    for src in glob.glob(os.path.join(DATA, "brief_*.html")):
        shutil.copy2(src, os.path.join(briefs_dir, os.path.basename(src)))
        copied += 1

    # Subscribe page: reuse the signup landing page if present.
    if os.path.exists(os.path.join("web", "index.html")):
        shutil.copy2(os.path.join("web", "index.html"),
                     os.path.join(out_dir, "subscribe.html"))

    pages = {
        "index.html": _chrome("Cited - autonomous AI newsroom", _index_page(pal), pal, "today"),
        "audit.html": _chrome("Cited - audit log", _audit_page(pal), pal, "audit"),
        "archive.html": _chrome("Cited - archive", _archive_page(pal), pal, "archive"),
    }
    for name, html in pages.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(html)

    # GitHub Pages: skip Jekyll processing.
    open(os.path.join(out_dir, ".nojekyll"), "w").close()

    entries = _read_audit()
    result = {"briefs": copied, "audit_entries": len(entries),
              "chain_intact": audit.verify_chain(AUDIT_LOG) if entries else True}
    print(f"site/ built: {copied} brief page(s), {len(entries)} audit entries, "
          f"chain_intact={result['chain_intact']}")
    return result


if __name__ == "__main__":
    build_site()
