"""
Control Plane write API (CP-03).

This module exposes limited write controls, currently:
- POST /control/call/hangup { session_id }

Implementation notes:
- Uses LiveKit RoomService.DeleteRoom to end the call for all participants
  (LiveKit telephony docs: hangup -> delete_room).
- Emits auditable OBS-00 events: control.command_received / control.command_applied.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from livekit import api

from .config import config
from observability.events import Component as ObsComponent, EventEmitter, Severity


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


