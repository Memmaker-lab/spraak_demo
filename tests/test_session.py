"""
CP-01: Session lifecycle tests.
Tests session creation, state transitions, and terminal states.
"""
import pytest
from datetime import datetime, timezone

from control_plane.session import Session, SessionState, SessionManager


class TestSession:
    """Test Session class."""
    
    def test_create_session_inbound(self):
        """Test creating inbound session."""
        session = Session(
            session_id="test-123",
            state=SessionState.INBOUND_RINGING,
            direction="inbound",
            created_at=datetime.now(timezone.utc),
            caller_number="+31612345678",
        )
        
        assert session.session_id == "test-123"
        assert session.direction == "inbound"
        assert session.state == SessionState.INBOUND_RINGING
        assert session.caller_number == "+31612345678"
        assert not session.is_terminal()
    
    def test_create_session_outbound(self):
        """Test creating outbound session."""
        session = Session(
            session_id="test-456",
            state=SessionState.CREATED,
            direction="outbound",
            created_at=datetime.now(timezone.utc),
            callee_number="+31612345678",
        )
        
        assert session.direction == "outbound"
        assert session.state == SessionState.CREATED
        assert session.callee_number == "+31612345678"
    
    def test_session_state_transition(self):
        """Test monotonic state transitions."""
        session = Session(
            session_id="test-789",
            state=SessionState.CREATED,
            direction="outbound",
            created_at=datetime.now(timezone.utc),
        )
        
        # Transition through states
        old_state = session.transition_to(SessionState.DIALING)
        assert old_state == SessionState.CREATED
        assert session.state == SessionState.DIALING
        
        old_state = session.transition_to(SessionState.RINGING)
        assert old_state == SessionState.DIALING
        assert session.state == SessionState.RINGING
        
        old_state = session.transition_to(SessionState.CONNECTED)
        assert old_state == SessionState.RINGING
        assert session.state == SessionState.CONNECTED
    
    def test_session_end(self):
        """Test ending a session."""
        session = Session(
            session_id="test-end",
            state=SessionState.CONNECTED,
            direction="inbound",
            created_at=datetime.now(timezone.utc),
        )
        
        session.end(reason="participant_left")
        
        assert session.state == SessionState.ENDED
        assert session.is_terminal()
        assert session.end_reason == "participant_left"
        assert session.ended_at is not None
    
    def test_invalid_direction(self):
        """Test that invalid direction raises error."""
        with pytest.raises(ValueError, match="direction must be"):
            Session(
                session_id="test-invalid",
                state=SessionState.CREATED,
                direction="invalid",
                created_at=datetime.now(timezone.utc),
            )


class TestSessionManager:
    """Test SessionManager class."""
    
    def test_create_inbound_session(self):
        """Test creating inbound session via manager."""
        manager = SessionManager()
        
        session = manager.create_session(
            direction="inbound",
            caller_number="+31612345678",
        )
        
        assert session.direction == "inbound"
        assert session.state == SessionState.INBOUND_RINGING
        assert session.caller_number == "+31612345678"
        assert session.session_id is not None
        assert len(session.session_id) > 0
    
    def test_create_outbound_session(self):
        """Test creating outbound session via manager."""
        manager = SessionManager()
        
        session = manager.create_session(
            direction="outbound",
            callee_number="+31612345678",
        )
        
        assert session.direction == "outbound"
        assert session.state == SessionState.CREATED
        assert session.callee_number == "+31612345678"
    
    def test_get_session(self):
        """Test retrieving session by ID."""
        manager = SessionManager()
        
        session = manager.create_session(direction="inbound")
        session_id = session.session_id
        
        retrieved = manager.get_session(session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session_id
    
    def test_get_session_by_room(self):
        """Test retrieving session by LiveKit room."""
        manager = SessionManager()
        
        session = manager.create_session(direction="inbound")
        session.livekit_room = "test-room-123"
        
        retrieved = manager.get_session_by_room("test-room-123")
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    def test_list_sessions_filtered(self):
        """Test listing sessions with filters."""
        manager = SessionManager()
        
        # Create multiple sessions
        session1 = manager.create_session(direction="inbound")
        session1.transition_to(SessionState.CONNECTED)
        
        session2 = manager.create_session(direction="outbound")
        session2.transition_to(SessionState.DIALING)
        
        session3 = manager.create_session(direction="inbound")
        session3.transition_to(SessionState.CONNECTED)
        
        # Filter by state
        connected = manager.list_sessions(state=SessionState.CONNECTED)
        assert len(connected) == 2
        
        # Filter by direction
        inbound = manager.list_sessions(direction="inbound")
        assert len(inbound) == 2
        
        # Filter by both
        inbound_connected = manager.list_sessions(
            state=SessionState.CONNECTED,
            direction="inbound",
        )
        assert len(inbound_connected) == 2

