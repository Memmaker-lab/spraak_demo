"""
OBS-00: Event emission tests.
Tests structured JSON event format per OBS-00.
"""
import json
import sys
from io import StringIO
from datetime import datetime

from control_plane.events import (
    EventEmitter,
    Component,
    Severity,
    control_plane_emitter,
)


class TestEventFormat:
    """Test event format per OBS-00 §2."""
    
    def test_required_fields(self):
        """Test that all required fields are present."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            emitter = EventEmitter(Component.CONTROL_PLANE)
            emitter.emit(
                event_type="test.event",
                session_id="test-session-123",
                severity=Severity.INFO,
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            # Required fields per OBS-00 §2.1
            assert "ts" in event
            assert "session_id" in event
            assert "component" in event
            assert "event_type" in event
            assert "severity" in event
            assert "correlation_id" in event
            assert "pii" in event
            
            # Check values
            assert event["session_id"] == "test-session-123"
            assert event["component"] == "control_plane"
            assert event["event_type"] == "test.event"
            assert event["severity"] == "info"
            
        finally:
            sys.stdout = old_stdout
    
    def test_timestamp_format(self):
        """Test that timestamp is RFC3339 format."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            emitter = EventEmitter(Component.CONTROL_PLANE)
            emitter.emit(
                event_type="test.event",
                session_id="test-session-123",
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            # Parse timestamp (should be RFC3339)
            ts = event["ts"]
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
            
        finally:
            sys.stdout = old_stdout
    
    def test_pii_field(self):
        """Test PII field structure."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            emitter = EventEmitter(Component.CONTROL_PLANE)
            emitter.emit(
                event_type="test.event",
                session_id="test-session-123",
                pii={
                    "contains_pii": True,
                    "fields": ["phone_number"],
                    "handling": "restricted",
                },
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            pii = event["pii"]
            assert pii["contains_pii"] is True
            assert "phone_number" in pii["fields"]
            assert pii["handling"] == "restricted"
            
        finally:
            sys.stdout = old_stdout
    
    def test_optional_fields(self):
        """Test optional fields per OBS-00 §2.2."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            emitter = EventEmitter(Component.CONTROL_PLANE)
            emitter.emit(
                event_type="test.event",
                session_id="test-session-123",
                call={"direction": "inbound", "caller_hash": "hash123"},
                livekit={"room": "test-room", "participant": "part123"},
                provider={"name": "test_provider", "model": "test_model"},
                latency_ms=42,
                attempt=1,
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            assert "call" in event
            assert event["call"]["direction"] == "inbound"
            assert "livekit" in event
            assert event["livekit"]["room"] == "test-room"
            assert "provider" in event
            assert event["provider"]["name"] == "test_provider"
            assert event["latency_ms"] == 42
            assert event["attempt"] == 1
            
        finally:
            sys.stdout = old_stdout


class TestEventTaxonomy:
    """Test event taxonomy per OBS-00 §3."""
    
    def test_call_started(self):
        """Test call.started event."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            control_plane_emitter.call_started(
                session_id="test-session",
                direction="inbound",
                caller_hash="hash123",
                livekit_room="test-room",
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            assert event["event_type"] == "call.started"
            assert event["call"]["direction"] == "inbound"
            assert event["call"]["caller_hash"] == "hash123"
            assert event["livekit"]["room"] == "test-room"
            
        finally:
            sys.stdout = old_stdout
    
    def test_call_answered(self):
        """Test call.answered event."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            control_plane_emitter.call_answered(
                session_id="test-session",
                livekit_room="test-room",
                livekit_participant="part123",
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            assert event["event_type"] == "call.answered"
            assert event["livekit"]["room"] == "test-room"
            assert event["livekit"]["participant"] == "part123"
            
        finally:
            sys.stdout = old_stdout
    
    def test_call_ended(self):
        """Test call.ended event."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            control_plane_emitter.call_ended(
                session_id="test-session",
                reason="participant_left",
                livekit_room="test-room",
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            assert event["event_type"] == "call.ended"
            assert event["reason"] == "participant_left"
            
        finally:
            sys.stdout = old_stdout
    
    def test_session_state_changed(self):
        """Test session.state_changed event."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            control_plane_emitter.session_state_changed(
                session_id="test-session",
                from_state="created",
                to_state="connected",
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            assert event["event_type"] == "session.state_changed"
            assert event["from_state"] == "created"
            assert event["to_state"] == "connected"
            
        finally:
            sys.stdout = old_stdout
    
    def test_livekit_events(self):
        """Test LiveKit lifecycle events."""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            # Room created
            control_plane_emitter.livekit_room_created(
                session_id="test-session",
                room="test-room",
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            assert event["event_type"] == "livekit.room.created"
            assert event["livekit"]["room"] == "test-room"
            
            # Reset
            sys.stdout = captured_output = StringIO()
            
            # Participant joined
            control_plane_emitter.livekit_participant_joined(
                session_id="test-session",
                room="test-room",
                participant="part123",
            )
            
            output = captured_output.getvalue().strip()
            event = json.loads(output)
            
            assert event["event_type"] == "livekit.participant.joined"
            assert event["livekit"]["room"] == "test-room"
            assert event["livekit"]["participant"] == "part123"
            
        finally:
            sys.stdout = old_stdout

