"""
Tests for Control Plane read API (CP-03).

Verifies:
- GET /control/sessions (list with filters)
- GET /control/sessions/{session_id} (session details)
- GET /control/sessions/{session_id}/events (query OBS-00 events)
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from control_plane.webhook_server import app
from control_plane.session import session_manager, SessionState
from observability.event_store import event_store
from observability.events import EventEmitter, Component, Severity


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_session():
    """Create a sample session for testing."""
    session = session_manager.create_session(
        direction="inbound",
        caller_number="+31612345678",
    )
    session.livekit_room = "call-_+31612345678_abc123"
    session.transition_to(SessionState.CONNECTED)
    return session


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up sessions and events between tests."""
    yield
    # Clear sessions
    session_manager._sessions.clear()
    # Clear events
    event_store._events.clear()


def test_list_sessions_empty(client):
    """Test listing sessions when none exist."""
    response = client.get("/control/sessions")
    assert response.status_code == 200
    assert response.json() == []


def test_list_sessions_all(client, sample_session):
    """Test listing all sessions."""
    # Create another session
    session2 = session_manager.create_session(direction="outbound", callee_number="+31687654321")
    
    response = client.get("/control/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Check session IDs are present
    session_ids = {s["session_id"] for s in data}
    assert sample_session.session_id in session_ids
    assert session2.session_id in session_ids


def test_list_sessions_filter_by_state(client, sample_session):
    """Test filtering sessions by state."""
    # Create an ended session
    ended_session = session_manager.create_session(direction="inbound")
    ended_session.end("test_reason")
    
    # Filter by connected
    response = client.get("/control/sessions?state=connected")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_id"] == sample_session.session_id
    assert data[0]["state"] == "connected"
    
    # Filter by ended
    response = client.get("/control/sessions?state=ended")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_id"] == ended_session.session_id


def test_list_sessions_filter_by_direction(client, sample_session):
    """Test filtering sessions by direction."""
    # Create outbound session
    outbound = session_manager.create_session(direction="outbound")
    
    # Filter by inbound
    response = client.get("/control/sessions?direction=inbound")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_id"] == sample_session.session_id
    assert data[0]["direction"] == "inbound"
    
    # Filter by outbound
    response = client.get("/control/sessions?direction=outbound")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_id"] == outbound.session_id


def test_list_sessions_invalid_state(client):
    """Test filtering with invalid state."""
    response = client.get("/control/sessions?state=invalid")
    assert response.status_code == 400
    assert "Invalid state" in response.json()["detail"]


def test_list_sessions_invalid_direction(client):
    """Test filtering with invalid direction."""
    response = client.get("/control/sessions?direction=invalid")
    assert response.status_code == 400
    assert "Invalid direction" in response.json()["detail"]


def test_get_session_details(client, sample_session):
    """Test getting session details."""
    response = client.get(f"/control/sessions/{sample_session.session_id}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["session_id"] == sample_session.session_id
    assert data["state"] == "connected"
    assert data["direction"] == "inbound"
    assert data["livekit_room"] == "call-_+31612345678_abc123"
    assert data["caller_number"] == "+31612345678"
    assert "created_at" in data


def test_get_session_not_found(client):
    """Test getting non-existent session."""
    response = client.get("/control/sessions/nonexistent")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_session_events_empty(client, sample_session):
    """Test querying events for session with no events."""
    response = client.get(f"/control/sessions/{sample_session.session_id}/events")
    assert response.status_code == 200
    data = response.json()
    
    assert data["session_id"] == sample_session.session_id
    assert data["events"] == []
    assert data["count"] == 0


def test_get_session_events_with_events(client, sample_session):
    """Test querying events for session with events."""
    # Emit some events
    emitter = EventEmitter(Component.CONTROL_PLANE)
    emitter.emit(
        "call.started",
        session_id=sample_session.session_id,
        severity=Severity.INFO,
        direction="inbound",
    )
    emitter.emit(
        "call.ended",
        session_id=sample_session.session_id,
        severity=Severity.INFO,
        reason="user_hangup",
    )
    
    # Query events
    response = client.get(f"/control/sessions/{sample_session.session_id}/events")
    assert response.status_code == 200
    data = response.json()
    
    assert data["session_id"] == sample_session.session_id
    assert len(data["events"]) == 2
    assert data["count"] == 2
    
    # Check event types
    event_types = {e["event_type"] for e in data["events"]}
    assert "call.started" in event_types
    assert "call.ended" in event_types


def test_get_session_events_filter_by_type(client, sample_session):
    """Test filtering events by event_type."""
    emitter = EventEmitter(Component.CONTROL_PLANE)
    emitter.emit("call.started", session_id=sample_session.session_id, severity=Severity.INFO)
    emitter.emit("call.ended", session_id=sample_session.session_id, severity=Severity.INFO, reason="test")
    
    response = client.get(
        f"/control/sessions/{sample_session.session_id}/events?event_type=call.started"
    )
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["events"]) == 1
    assert data["events"][0]["event_type"] == "call.started"


def test_get_session_events_filter_by_component(client, sample_session):
    """Test filtering events by component."""
    emitter_cp = EventEmitter(Component.CONTROL_PLANE)
    emitter_vp = EventEmitter(Component.VOICE_PIPELINE)
    
    emitter_cp.emit("call.started", session_id=sample_session.session_id, severity=Severity.INFO)
    emitter_vp.emit("turn.started", session_id=sample_session.session_id, severity=Severity.INFO)
    
    response = client.get(
        f"/control/sessions/{sample_session.session_id}/events?component=control_plane"
    )
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["events"]) == 1
    assert data["events"][0]["component"] == "control_plane"


def test_get_session_events_filter_by_time(client, sample_session):
    """Test filtering events by time range."""
    emitter = EventEmitter(Component.CONTROL_PLANE)
    
    # Emit event now
    emitter.emit("call.started", session_id=sample_session.session_id, severity=Severity.INFO)
    
    # Query with since filter (should include the event)
    # Use a timestamp slightly in the past to ensure we capture the event
    # Format: YYYY-MM-DDTHH:MM:SS+00:00 (no microseconds, explicit timezone)
    since = datetime.now(timezone.utc).replace(microsecond=0)
    since_str = since.isoformat()
    response = client.get(
        f"/control/sessions/{sample_session.session_id}/events?since={since_str}"
    )
    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert len(data["events"]) >= 1
    
    # Query with future since (should exclude the event)
    # Use a timestamp far in the future
    future = datetime.now(timezone.utc).replace(year=2099, microsecond=0)
    future_str = future.isoformat()
    response = client.get(
        f"/control/sessions/{sample_session.session_id}/events?since={future_str}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 0


def test_get_session_events_limit(client, sample_session):
    """Test limiting number of events returned."""
    emitter = EventEmitter(Component.CONTROL_PLANE)
    
    # Emit multiple events
    for i in range(5):
        emitter.emit(
            "call.started",
            session_id=sample_session.session_id,
            severity=Severity.INFO,
            test_index=i,
        )
    
    # Query with limit
    response = client.get(
        f"/control/sessions/{sample_session.session_id}/events?limit=3"
    )
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["events"]) == 3
    assert data["count"] == 3


def test_get_session_events_not_found(client):
    """Test querying events for non-existent session."""
    response = client.get("/control/sessions/nonexistent/events")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_session_events_invalid_timestamp(client, sample_session):
    """Test querying with invalid timestamp."""
    response = client.get(
        f"/control/sessions/{sample_session.session_id}/events?since=invalid"
    )
    assert response.status_code == 400
    assert "Invalid since timestamp" in response.json()["detail"]

