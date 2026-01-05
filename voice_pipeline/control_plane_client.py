"""
Voice Pipeline -> Control Plane client.

Used for best-effort call control actions without embedding control logic in the pipeline.
The pipeline emits its own UX/voice events and then requests the Control Plane to apply
telephony control actions (CP-03).
"""

from __future__ import annotations

import os
from typing import Optional

import aiohttp


def get_control_plane_base_url() -> Optional[str]:
    """
    Base URL for Control Plane HTTP API, e.g. http://127.0.0.1:8000
    """
    url = os.getenv("CONTROL_PLANE_URL")
    if not url:
        return None
    return url.rstrip("/")


async def request_hangup(session_id: str) -> bool:
    """
    Best-effort request to Control Plane to hang up a call by session_id.

    Returns True if request was sent and succeeded (2xx), False otherwise.
    """
    base = get_control_plane_base_url()
    if not base:
        return False

    endpoint = f"{base}/control/call/hangup"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(endpoint, json={"session_id": session_id}, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return 200 <= resp.status < 300
    except Exception:
        return False


