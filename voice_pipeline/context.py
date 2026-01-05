"""
Voice Pipeline context extraction.

Documentation-first:
- LiveKit job metadata is available in JobContext as a freeform string and is
  commonly JSON (see LiveKit Agents docs: Job lifecycle -> metadata).

This module provides helpers to:
- Parse job metadata JSON safely
- Resolve session_id from job metadata / participant attributes with fallback
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class DispatchContext:
    """Parsed context derived from LiveKit dispatch / participant."""

    session_id: str
    flow: Optional[str] = None
    metadata_raw: Optional[str] = None


def parse_job_metadata(metadata: Optional[str]) -> dict[str, Any]:
    """
    Parse JobContext.job.metadata.

    LiveKit specifies this is a freeform string; JSON is recommended.
    Returns {} if metadata is missing or not valid JSON.
    """
    if not metadata:
        return {}
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def resolve_session_id(
    *,
    room_name: str,
    job_metadata: Optional[str],
    participant_attributes: Optional[Mapping[str, str]] = None,
) -> str:
    """
    Resolve the OBS-00 session_id.

    Priority:
    1) job metadata JSON key "session_id"
    2) participant attributes key "session_id"
    3) fallback: room name
    """
    md = parse_job_metadata(job_metadata)
    md_session_id = md.get("session_id")
    if isinstance(md_session_id, str) and md_session_id.strip():
        return md_session_id.strip()

    if participant_attributes:
        attr_session_id = participant_attributes.get("session_id")
        if isinstance(attr_session_id, str) and attr_session_id.strip():
            return attr_session_id.strip()

    # Safe fallback: room name is opaque and correlates well across systems.
    return room_name or "unknown"


def build_dispatch_context(
    *,
    room_name: str,
    job_metadata: Optional[str],
    participant_attributes: Optional[Mapping[str, str]] = None,
) -> DispatchContext:
    """
    Build a single context object used by the pipeline.
    """
    md = parse_job_metadata(job_metadata)
    session_id = resolve_session_id(
        room_name=room_name,
        job_metadata=job_metadata,
        participant_attributes=participant_attributes,
    )
    flow = md.get("flow") if isinstance(md.get("flow"), str) else None
    return DispatchContext(session_id=session_id, flow=flow, metadata_raw=job_metadata)


