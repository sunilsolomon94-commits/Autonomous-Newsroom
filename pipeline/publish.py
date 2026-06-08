"""[CREDENTIALED] Platform adapters. Each upload sets the platform's AI-synthetic-
media disclosure flag and uses the standard description template.

Scaffolded to daily_run's call signature: send(video, shorts, persona). A later
milestone implements YouTube Data API (scheduled Premiere for long form, native
Shorts), Instagram Graph API (Reels), X API v2 (native video), and LinkedIn API
(native video), each staggered 30-60 min.
"""
from __future__ import annotations


def send(video: str, shorts: list[str], persona: dict) -> dict:
    raise NotImplementedError(
        "BUILD: implement per-platform adapters. Every upload "
        "must set the AI-generated disclosure flag and stagger posts 30-60 min.")
