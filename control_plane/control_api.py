"""
Control Plane API (CP-03).

This module exposes:
- Read API: list sessions, get session details, query events
- Write API: hangup calls

Implementation notes:
- Uses LiveKit RoomService.DeleteRoom to end the call for all participants
  (LiveKit telephony docs: hangup -> delete_room).
- Emits auditable OBS-00 events: control.command_received / control.command_applied.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from livekit import api

from .config import config
from .session import session_manager, SessionState
from observability.events import Component as ObsComponent, EventEmitter, Severity
from observability.event_store import event_store


router = APIRouter(prefix="/control", tags=["control"])
emitter = EventEmitter(ObsComponent.CONTROL_PLANE)


class HangupRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="Opaque session_id (inbound: room name)")


class HangupResponse(BaseModel):
    status: str


def _new_correlation_id() -> str:
    return f"cmd_{int(time.time() * 1000)}"


async def _delete_room(room_name: str) -> None:
    """
    End the call for all participants by deleting the LiveKit room.
    """
    lk = api.LiveKitAPI(
        url=config.livekit_url,
        api_key=config.livekit_api_key,
        api_secret=config.livekit_api_secret,
    )
    try:
        await lk.room.delete_room(api.DeleteRoomRequest(room=room_name))
    finally:
        await lk.aclose()


@router.post("/call/hangup", response_model=HangupResponse)
async def hangup_call(req: HangupRequest) -> HangupResponse:
    """
    Hang up / cancel a call by session_id.

    For inbound calls, we treat session_id as the room name (call-...).
    """
    correlation_id = _new_correlation_id()

    emitter.emit(
        "control.command_received",
        session_id=req.session_id,
        severity=Severity.INFO,
        correlation_id=correlation_id,
        command="call.hangup",
    )

    try:
        await _delete_room(req.session_id)
    except Exception as e:
        # Stable error surface (CP-03): no internal traces
        emitter.emit(
            "control.command_applied",
            session_id=req.session_id,
            severity=Severity.ERROR,
            correlation_id=correlation_id,
            command="call.hangup",
            result="error",
            error_class=type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="hangup_failed")

    emitter.emit(
        "control.command_applied",
        session_id=req.session_id,
        severity=Severity.INFO,
        correlation_id=correlation_id,
        command="call.hangup",
        result="ok",
    )

    return HangupResponse(status="ok")


# --- Read API (CP-03) ---


class SessionSummary(BaseModel):
    """Session summary for list endpoint."""
    session_id: str
    state: str
    direction: str
    created_at: str
    ended_at: Optional[str] = None
    end_reason: Optional[str] = None
    livekit_room: Optional[str] = None


class SessionDetail(BaseModel):
    """Full session details."""
    session_id: str
    state: str
    direction: str
    created_at: str
    ended_at: Optional[str] = None
    end_reason: Optional[str] = None
    livekit_room: Optional[str] = None
    livekit_participant: Optional[str] = None
    caller_number: Optional[str] = None
    callee_number: Optional[str] = None
    config: dict = Field(default_factory=dict)


@router.get("/sessions", response_model=List[SessionSummary])
async def list_sessions(
    state: Optional[str] = Query(None, description="Filter by state (created, connected, ended, etc.)"),
    direction: Optional[str] = Query(None, description="Filter by direction (inbound, outbound)"),
) -> List[SessionSummary]:
    """
    List sessions with optional filters (CP-03 read API).
    
    Returns session summaries (not full details) for efficient listing.
    """
    # Parse state filter
    state_filter: Optional[SessionState] = None
    if state:
        try:
            state_filter = SessionState(state.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid state: {state}")
    
    # Validate direction filter
    if direction and direction not in ("inbound", "outbound"):
        raise HTTPException(status_code=400, detail=f"Invalid direction: {direction}")
    
    sessions = session_manager.list_sessions(state=state_filter, direction=direction)
    
    # Convert to summaries
    summaries = []
    for s in sessions:
        summaries.append(SessionSummary(
            session_id=s.session_id,
            state=s.state.value,
            direction=s.direction,
            created_at=s.created_at.isoformat(),
            ended_at=s.ended_at.isoformat() if s.ended_at else None,
            end_reason=s.end_reason,
            livekit_room=s.livekit_room,
        ))
    
    return summaries


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    """
    Get session details by session_id (CP-03 read API).
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionDetail(
        session_id=session.session_id,
        state=session.state.value,
        direction=session.direction,
        created_at=session.created_at.isoformat(),
        ended_at=session.ended_at.isoformat() if session.ended_at else None,
        end_reason=session.end_reason,
        livekit_room=session.livekit_room,
        livekit_participant=session.livekit_participant,
        caller_number=session.caller_number,
        callee_number=session.callee_number,
        config=session.config,
    )


@router.get("/sessions/{session_id}/events")
async def get_session_events(
    session_id: str,
    event_type: Optional[str] = Query(None, description="Filter by event_type"),
    component: Optional[str] = Query(None, description="Filter by component"),
    since: Optional[str] = Query(None, description="ISO timestamp (inclusive)"),
    until: Optional[str] = Query(None, description="ISO timestamp (inclusive)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Max events to return"),
) -> dict:
    """
    Query OBS-00 events for a session (CP-03 read API).
    
    Returns structured events per OBS-00 contract.
    """
    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Parse timestamps (support ISO format with or without timezone)
    # Note: FastAPI automatically URL-decodes query params, but + may become space
    since_dt: Optional[datetime] = None
    if since:
        try:
            # Handle URL-encoded + (may appear as space)
            since_clean = since.replace(" ", "+").replace("Z", "+00:00")
            # If no timezone indicator, assume UTC
            if "+" not in since_clean and "-" not in since_clean[-6:]:
                since_clean += "+00:00"
            since_dt = datetime.fromisoformat(since_clean)
        except (ValueError, AttributeError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid since timestamp: {since}")
    
    until_dt: Optional[datetime] = None
    if until:
        try:
            # Handle URL-encoded + (may appear as space)
            until_clean = until.replace(" ", "+").replace("Z", "+00:00")
            # If no timezone indicator, assume UTC
            if "+" not in until_clean and "-" not in until_clean[-6:]:
                until_clean += "+00:00"
            until_dt = datetime.fromisoformat(until_clean)
        except (ValueError, AttributeError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid until timestamp: {until}")
    
    # Query events
    events = event_store.query(
        session_id=session_id,
        event_type=event_type,
        component=component,
        since=since_dt,
        until=until_dt,
        limit=limit,
    )
    
    return {
        "session_id": session_id,
        "events": events,
        "count": len(events),
    }


