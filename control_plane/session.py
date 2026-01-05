"""
CP-01: Session lifecycle management.
Each call has exactly one session_id with explicit, monotonic states.
"""
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timezone


class SessionState(str, Enum):
    """Session states per CP-01 (monotonic progression)."""
    CREATED = "created"
    DIALING = "dialing"
    RINGING = "ringing"
    INBOUND_RINGING = "inbound_ringing"
    CONNECTED = "connected"
    ENDING = "ending"
    ENDED = "ended"


@dataclass
class Session:
    """Represents a call session per CP-01."""
    
    session_id: str
    state: SessionState
    direction: str  # "inbound" | "outbound"
    created_at: datetime
    
    # LiveKit correlation
    livekit_room: Optional[str] = None
    livekit_participant: Optional[str] = None
    
    # Call metadata
    caller_number: Optional[str] = None  # Raw phone number (PII allowed per OBS-00)
    callee_number: Optional[str] = None
    
    # Configuration (for voice pipeline)
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Termination
    ended_at: Optional[datetime] = None
    end_reason: Optional[str] = None
    
    def __post_init__(self):
        """Validate session state."""
        if not self.session_id:
            raise ValueError("session_id is required")
        if not self.direction in ("inbound", "outbound"):
            raise ValueError("direction must be 'inbound' or 'outbound'")
    
    def transition_to(self, new_state: SessionState) -> SessionState:
        """
        Transition to a new state (monotonic).
        Returns the previous state.
        """
        old_state = self.state
        self.state = new_state
        return old_state
    
    def end(self, reason: str) -> None:
        """Mark session as ended."""
        self.transition_to(SessionState.ENDING)
        self.transition_to(SessionState.ENDED)
        self.ended_at = datetime.now(timezone.utc)
        self.end_reason = reason
    
    def is_terminal(self) -> bool:
        """Check if session is in a terminal state."""
        return self.state == SessionState.ENDED


class SessionManager:
    """Manages session lifecycle per CP-01."""
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
    
    def create_session(
        self,
        direction: str,
        caller_number: Optional[str] = None,
        callee_number: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """
        Create a new session per CP-01.
        session_id is opaque and does not encode PII.
        """
        session_id = str(uuid.uuid4())
        
        # Initial state based on direction
        if direction == "inbound":
            initial_state = SessionState.INBOUND_RINGING
        else:
            initial_state = SessionState.CREATED
        
        session = Session(
            session_id=session_id,
            state=initial_state,
            direction=direction,
            created_at=datetime.now(timezone.utc),
            caller_number=caller_number,
            callee_number=callee_number,
            config=config or {},
        )
        
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self._sessions.get(session_id)
    
    def get_session_by_room(self, room_name: str) -> Optional[Session]:
        """Get session by LiveKit room name."""
        for session in self._sessions.values():
            if session.livekit_room == room_name:
                return session
        return None
    
    def list_sessions(
        self,
        state: Optional[SessionState] = None,
        direction: Optional[str] = None,
    ) -> list[Session]:
        """List sessions with optional filters."""
        sessions = list(self._sessions.values())
        
        if state:
            sessions = [s for s in sessions if s.state == state]
        if direction:
            sessions = [s for s in sessions if s.direction == direction]
        
        return sessions


# Global session manager
session_manager = SessionManager()

