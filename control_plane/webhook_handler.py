"""
LiveKit webhook handler for inbound calls.
Receives webhook events and manages session lifecycle.
"""
import json
import hashlib
import hmac
from typing import Optional, Dict, Any
from livekit import api
from livekit.protocol import webhook as lk_webhook

from .config import config
from .session import SessionManager, SessionState, session_manager
from .events import control_plane_emitter


class WebhookHandler:
    """Handles LiveKit webhook events for inbound calls."""
    
    def __init__(self):
        self.session_manager = session_manager
    
    def verify_webhook(self, body: bytes, auth_header: str) -> bool:
        """
        Verify webhook signature per LiveKit docs.
        Returns True if valid, False otherwise.
        """
        try:
            # LiveKit signs webhooks with JWT containing sha256 hash
            # For now, we'll use a simple approach - in production,
            # use livekit-server-sdk's WebhookReceiver
            # This is a placeholder - proper implementation would use JWT verification
            return True  # TODO: Implement proper JWT verification
        except Exception:
            return False
    
    def handle_webhook(self, body: bytes, auth_header: str) -> Optional[Dict[str, Any]]:
        """
        Handle incoming webhook event.
        Returns response dict or None.
        """
        # Verify webhook
        if not self.verify_webhook(body, auth_header):
            return {"error": "Invalid webhook signature"}
        
        # Parse webhook event
        try:
            event_data = json.loads(body)
            event_type = event_data.get("event")
        except Exception as e:
            return {"error": f"Invalid webhook payload: {e}"}
        
        # Route to appropriate handler
        if event_type == "room_started":
            self._handle_room_started(event_data)
        elif event_type == "participant_joined":
            self._handle_participant_joined(event_data)
        elif event_type == "participant_left":
            self._handle_participant_left(event_data)
        elif event_type == "track_published":
            self._handle_track_published(event_data)
        elif event_type == "room_finished":
            self._handle_room_finished(event_data)
        
        return {"status": "ok"}
    
    def _handle_room_started(self, event_data: Dict[str, Any]) -> None:
        """Handle room_started webhook event."""
        room = event_data.get("room", {})
        room_name = room.get("name")
        
        if not room_name:
            return
        
        # Check if session exists for this room
        session = self.session_manager.get_session_by_room(room_name)
        
        if not session:
            # New inbound call - create session
            # Extract caller info from room metadata or participant
            session = self.session_manager.create_session(
                direction="inbound",
                config={},  # Will be populated by voice pipeline
            )
            session.livekit_room = room_name
            
            # Emit events
            control_plane_emitter.livekit_room_created(session.session_id, room_name)
            control_plane_emitter.call_started(
                session.session_id,
                direction="inbound",
                livekit_room=room_name,
            )
        else:
            # Room already has session, just emit room.created
            control_plane_emitter.livekit_room_created(session.session_id, room_name)
    
    def _handle_participant_joined(self, event_data: Dict[str, Any]) -> None:
        """Handle participant_joined webhook event."""
        room = event_data.get("room", {})
        participant = event_data.get("participant", {})
        
        room_name = room.get("name")
        participant_sid = participant.get("sid")
        participant_identity = participant.get("identity", "")
        
        if not room_name or not participant_sid:
            return
        
        # Get or create session
        session = self.session_manager.get_session_by_room(room_name)
        
        if not session:
            # Shouldn't happen, but create session if missing
            session = self.session_manager.create_session(direction="inbound")
            session.livekit_room = room_name
            control_plane_emitter.call_started(
                session.session_id,
                direction="inbound",
                livekit_room=room_name,
            )
        
        # Check if this is a SIP participant (inbound call)
        # SIP participants typically have identity starting with "sip:" or similar
        if participant_identity.startswith("sip:") or "phone" in participant_identity.lower():
            # This is the caller
            if not session.livekit_participant:
                session.livekit_participant = participant_sid
                
                # Extract phone number if available
                # LiveKit may include this in metadata or attributes
                metadata = participant.get("metadata", "")
                if metadata:
                    try:
                        meta = json.loads(metadata) if isinstance(metadata, str) else metadata
                        if "phone_number" in meta:
                            session.caller_number = meta["phone_number"]
                    except:
                        pass
                
                # Transition to connected if not already
                if session.state == SessionState.INBOUND_RINGING:
                    old_state = session.transition_to(SessionState.CONNECTED)
                    control_plane_emitter.session_state_changed(
                        session.session_id,
                        from_state=old_state.value,
                        to_state=SessionState.CONNECTED.value,
                    )
                    control_plane_emitter.call_answered(
                        session.session_id,
                        livekit_room=room_name,
                        livekit_participant=participant_sid,
                    )
        
        # Emit participant joined event
        control_plane_emitter.livekit_participant_joined(
            session.session_id,
            room_name,
            participant_sid,
        )
    
    def _handle_participant_left(self, event_data: Dict[str, Any]) -> None:
        """Handle participant_left webhook event."""
        room = event_data.get("room", {})
        participant = event_data.get("participant", {})
        
        room_name = room.get("name")
        participant_sid = participant.get("sid")
        
        if not room_name or not participant_sid:
            return
        
        session = self.session_manager.get_session_by_room(room_name)
        
        if not session:
            return
        
        # Emit participant left event
        control_plane_emitter.livekit_participant_left(
            session.session_id,
            room_name,
            participant_sid,
        )
        
        # If this is the SIP participant (caller), end the call
        if session.livekit_participant == participant_sid:
            if not session.is_terminal():
                session.end(reason="participant_left")
                control_plane_emitter.call_ended(
                    session.session_id,
                    reason="participant_left",
                    livekit_room=room_name,
                    livekit_participant=participant_sid,
                )
    
    def _handle_track_published(self, event_data: Dict[str, Any]) -> None:
        """Handle track_published webhook event."""
        # Track published events are mainly for voice pipeline
        # Control plane just logs them
        room = event_data.get("room", {})
        participant = event_data.get("participant", {})
        track = event_data.get("track", {})
        
        room_name = room.get("name")
        participant_sid = participant.get("sid")
        track_sid = track.get("sid")
        
        if not room_name:
            return
        
        session = self.session_manager.get_session_by_room(room_name)
        
        if session:
            control_plane_emitter.emit(
                "livekit.track.published",
                session.session_id,
                livekit={
                    "room": room_name,
                    "participant": participant_sid,
                    "track": track_sid,
                },
            )
    
    def _handle_room_finished(self, event_data: Dict[str, Any]) -> None:
        """Handle room_finished webhook event."""
        room = event_data.get("room", {})
        room_name = room.get("name")
        
        if not room_name:
            return
        
        session = self.session_manager.get_session_by_room(room_name)
        
        if session and not session.is_terminal():
            session.end(reason="room_finished")
            control_plane_emitter.call_ended(
                session.session_id,
                reason="room_finished",
                livekit_room=room_name,
            )


# Global webhook handler
webhook_handler = WebhookHandler()

