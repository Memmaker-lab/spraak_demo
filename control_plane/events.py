"""
OBS-00: Structured JSON event emission.
All events follow the OBS-00 contract.
"""
import json
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Literal
from enum import Enum


class Component(str, Enum):
    """Component types per OBS-00."""
    CONTROL_PLANE = "control_plane"
    VOICE_PIPELINE = "voice_pipeline"
    ADAPTER = "adapter"
    ACTION_RUNNER = "action_runner"


class Severity(str, Enum):
    """Event severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class EventEmitter:
    """Emits structured JSON events per OBS-00."""
    
    def __init__(self, component: Component):
        self.component = component
    
    def emit(
        self,
        event_type: str,
        session_id: str,
        severity: Severity = Severity.INFO,
        correlation_id: Optional[str] = None,
        pii: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Emit a structured JSON event per OBS-00.
        
        Args:
            event_type: Stable event type string (e.g., "call.started")
            session_id: Opaque session identifier
            severity: Event severity level
            correlation_id: Optional correlation ID for request/turn/action
            pii: PII metadata dict with contains_pii, fields, handling
            **kwargs: Additional event-specific fields
        """
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "component": self.component.value,
            "event_type": event_type,
            "severity": severity.value,
            "correlation_id": correlation_id or session_id,
            "pii": pii or {"contains_pii": False, "fields": [], "handling": "none"},
        }
        
        # Add any additional fields
        event.update(kwargs)
        
        # Emit as JSON to stdout (can be redirected to file/log aggregator)
        json.dump(event, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
    
    def call_started(
        self,
        session_id: str,
        direction: Literal["inbound", "outbound"],
        caller_hash: Optional[str] = None,
        callee_hash: Optional[str] = None,
        livekit_room: Optional[str] = None,
        livekit_participant: Optional[str] = None,
    ) -> None:
        """Emit call.started event."""
        call_data = {"direction": direction}
        if caller_hash:
            call_data["caller_hash"] = caller_hash
        if callee_hash:
            call_data["callee_hash"] = callee_hash
        
        livekit_data = {}
        if livekit_room:
            livekit_data["room"] = livekit_room
        if livekit_participant:
            livekit_data["participant"] = livekit_participant
        
        self.emit(
            "call.started",
            session_id,
            call=call_data,
            livekit=livekit_data if livekit_data else None,
        )
    
    def call_answered(
        self,
        session_id: str,
        livekit_room: Optional[str] = None,
        livekit_participant: Optional[str] = None,
    ) -> None:
        """Emit call.answered event."""
        livekit_data = {}
        if livekit_room:
            livekit_data["room"] = livekit_room
        if livekit_participant:
            livekit_data["participant"] = livekit_participant
        
        self.emit(
            "call.answered",
            session_id,
            livekit=livekit_data if livekit_data else None,
        )
    
    def call_ended(
        self,
        session_id: str,
        reason: str,
        livekit_room: Optional[str] = None,
        livekit_participant: Optional[str] = None,
    ) -> None:
        """Emit call.ended event."""
        livekit_data = {}
        if livekit_room:
            livekit_data["room"] = livekit_room
        if livekit_participant:
            livekit_data["participant"] = livekit_participant
        
        self.emit(
            "call.ended",
            session_id,
            reason=reason,
            livekit=livekit_data if livekit_data else None,
        )
    
    def session_state_changed(
        self,
        session_id: str,
        from_state: str,
        to_state: str,
    ) -> None:
        """Emit session.state_changed event."""
        self.emit(
            "session.state_changed",
            session_id,
            from_state=from_state,
            to_state=to_state,
        )
    
    def livekit_room_created(
        self,
        session_id: str,
        room: str,
    ) -> None:
        """Emit livekit.room.created event."""
        self.emit(
            "livekit.room.created",
            session_id,
            livekit={"room": room},
        )
    
    def livekit_participant_joined(
        self,
        session_id: str,
        room: str,
        participant: str,
    ) -> None:
        """Emit livekit.participant.joined event."""
        self.emit(
            "livekit.participant.joined",
            session_id,
            livekit={"room": room, "participant": participant},
        )
    
    def livekit_participant_left(
        self,
        session_id: str,
        room: str,
        participant: str,
    ) -> None:
        """Emit livekit.participant.left event."""
        self.emit(
            "livekit.participant.left",
            session_id,
            livekit={"room": room, "participant": participant},
        )
    
    def provider_event(
        self,
        session_id: str,
        category: str,
        direction: Optional[Literal["inbound", "outbound"]] = None,
        provider_name: Optional[str] = None,
        detail: Optional[str] = None,
        livekit_room: Optional[str] = None,
        livekit_participant: Optional[str] = None,
    ) -> None:
        """Emit provider.event (for errors/limits per CP-04)."""
        provider_data = {}
        if provider_name:
            provider_data["name"] = provider_name
        
        livekit_data = {}
        if livekit_room:
            livekit_data["room"] = livekit_room
        if livekit_participant:
            livekit_data["participant"] = livekit_participant
        
        self.emit(
            "provider.event",
            session_id,
            severity=Severity.WARN if "error" in category or "limited" in category else Severity.INFO,
            category=category,
            direction=direction,
            provider=provider_data if provider_data else None,
            detail=detail,
            livekit=livekit_data if livekit_data else None,
        )


# Global event emitter for control plane
control_plane_emitter = EventEmitter(Component.CONTROL_PLANE)

