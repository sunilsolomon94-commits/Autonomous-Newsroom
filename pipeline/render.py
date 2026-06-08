"""[CREDENTIALED] Render the anchor script to an avatar video.

Default provider: HeyGen (chosen for API maturity and reliability in an
automated daily pipeline). Provider-agnostic by design: switch in persona.yaml
to joggai (free fallback) or deepbrain (regional-language scale) later.

Verify endpoint paths and field names against current HeyGen API docs before
the first live run, since provider APIs change.
"""
from __future__ import annotations
import os
import time
import requests

HEYGEN_GENERATE = "https://api.heygen.com/v2/video/generate"
HEYGEN_STATUS = "https://api.heygen.com/v1/video_status.get"


def to_video(script_text: str, persona: dict) -> str:
    provider = persona["anchor"]["voice_provider"]
    if provider == "heygen":
        return _heygen(script_text, persona)
    # TODO(claude-code): joggai and deepbrain adapters share this signature.
    raise NotImplementedError(f"provider not wired: {provider}")


def _heygen(script_text: str, persona: dict) -> str:
    key = os.environ["HEYGEN_API_KEY"]
    a = persona["anchor"]
    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    body = {
        "video_inputs": [{
            "character": {"type": "avatar", "avatar_id": a["avatar_id"]},
            "voice": {"type": "text", "input_text": script_text, "voice_id": a["voice_id"]},
        }],
        # 9:16 vertical first, matches persona.format.aspect_primary
        "dimension": {"width": 720, "height": 1280},
    }
    r = requests.post(HEYGEN_GENERATE, json=body, headers=headers, timeout=60)
    r.raise_for_status()
    video_id = r.json()["data"]["video_id"]

    # Poll until the render completes.
    for _ in range(120):  # up to ~10 min at 5s
        s = requests.get(HEYGEN_STATUS, params={"video_id": video_id}, headers=headers, timeout=30)
        s.raise_for_status()
        data = s.json()["data"]
        if data["status"] == "completed":
            return data["video_url"]
        if data["status"] == "failed":
            raise RuntimeError(f"render failed: {data.get('error')}")
        time.sleep(5)
    raise TimeoutError("render did not complete in time")
