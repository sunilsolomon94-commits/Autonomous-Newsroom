"""[CREDENTIALED for news API] Pull stories from RSS, a news API, and GDELT.

RSS and GDELT need no key. NEWS_API_KEY unlocks the news API tier. Returns raw
items: {id, url, tier, publisher, title, body, ts}. One bad feed never kills a run.
"""
from __future__ import annotations
import os
import hashlib
import datetime as dt
import yaml
import requests

try:
    import feedparser
except ImportError:
    feedparser = None

UA = {"User-Agent": "CitedNewsroom/1.0"}


def _id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _tier_num(name: str) -> int:
    return int(name.replace("tier", ""))


def _from_rss(url: str, tier: int) -> list[dict]:
    if not feedparser:
        return []
    out = []
    feed = feedparser.parse(url)
    publisher = feed.feed.get("title", url)
    for e in feed.entries[:25]:
        link = e.get("link", "")
        if not link:
            continue
        out.append({
            "id": _id(link), "url": link, "tier": tier, "publisher": publisher,
            "title": e.get("title", ""), "body": e.get("summary", ""),
            "ts": e.get("published", dt.datetime.utcnow().isoformat()),
        })
    return out


def _from_newsapi(key: str, tier: int) -> list[dict]:
    try:
        r = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"category": "technology", "language": "en", "pageSize": 50},
            headers={**UA, "X-Api-Key": key}, timeout=30)
        r.raise_for_status()
        out = []
        for a in r.json().get("articles", []):
            url = a.get("url", "")
            if not url:
                continue
            out.append({
                "id": _id(url), "url": url, "tier": tier,
                "publisher": (a.get("source") or {}).get("name", "newsapi"),
                "title": a.get("title", ""), "body": a.get("description", ""),
                "ts": a.get("publishedAt", "")})
        return out
    except Exception:
        return []


def fetch_all(sources_path: str) -> list[dict]:
    cfg = yaml.safe_load(open(sources_path))
    items: list[dict] = []
    for tier_name, block in cfg.get("tiers", {}).items():
        tier = _tier_num(tier_name)
        for feed in block.get("feeds", []):
            if str(feed).startswith("http"):
                try:
                    items += _from_rss(feed, tier)
                except Exception:
                    continue
            # named sources (gdelt, hackernews_frontpage) are wired separately
    key = os.environ.get("NEWS_API_KEY")
    if key:
        items += _from_newsapi(key, tier=2)
    seen, deduped = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        deduped.append(it)
    return deduped
