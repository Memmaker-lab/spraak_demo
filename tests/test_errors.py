"""
CP-04: Provider error handling tests (ENFORCED).
Tests MUST exist and MUST pass per CP-04 §6.
"""
import pytest
from control_plane.errors import (
    ProviderErrorHandler,
    ProviderErrorCategory,
)
from control_plane.session import SessionManager, SessionState
from control_plane.events import EventEmitter, Component, Severity
import json
import sys
from io import StringIO


class TestProviderErrorClassification:
    """Test error classification per CP-04 §2."""
    
    def test_auth_failed(self):
        """Test auth_failed classification."""
        error = Exception("Authentication failed")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.AUTH_FAILED
        
        error = Exception("Unauthorized: 401")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.AUTH_FAILED
    
    def test_misconfigured(self):
        """Test misconfigured classification."""
        error = Exception("Trunk misconfigured")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.MISCONFIGURED
    
    def test_network_error(self):
        """Test network_error classification."""
        error = Exception("Network timeout")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.NETWORK_ERROR
        
        error = Exception("Connection refused")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.NETWORK_ERROR
    
    def test_busy(self):
        """Test busy classification."""
        error = Exception("Number is busy")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.BUSY
        
        error = Exception("486 Busy Here")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.BUSY
    
    def test_no_answer(self):
        """Test no_answer classification."""
        error = Exception("No answer")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.NO_ANSWER
        
        error = Exception("480 Temporarily Unavailable")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.NO_ANSWER
    
    def test_rejected(self):
        """Test rejected classification."""
        error = Exception("Call rejected")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.REJECTED
        
        error = Exception("603 Decline")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.REJECTED
    
    def test_rate_limited(self):
        """Test rate_limited classification."""
        error = Exception("Rate limit exceeded")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.RATE_LIMITED
        
        error = Exception("429 Too Many Requests")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.RATE_LIMITED
    
    def test_capacity_limited(self):
        """Test capacity_limited classification."""
        error = Exception("Capacity exceeded")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.CAPACITY_LIMITED
        
        error = Exception("503 Service Unavailable")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.CAPACITY_LIMITED
    
    def test_unknown_error(self):
        """Test unknown_error classification."""
        error = Exception("Something weird happened")
        category = ProviderErrorHandler.classify_error(error)
        assert category == ProviderErrorCategory.UNKNOWN_ERROR


class TestProviderErrorHandling:
    """Test error handling per CP-04 §3 and §4."""
    
    def test_error_handling_emits_events(self):
        """Test that error handling emits provider.event and call.ended."""
        # Capture stdout for event emission
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            session_manager = SessionManager()
            session = session_manager.create_session(direction="inbound")
            
            error = Exception("Rate limit exceeded")
            category = ProviderErrorHandler.handle_error(
                session_id=session.session_id,
                error=error,
                direction="inbound",
                provider_name="test_provider",
                livekit_room="test-room",
            )
            
            # End the session
            session.end(reason=category)
            
            # Check events were emitted
            output = captured_output.getvalue()
            assert "provider.event" in output
            assert category in output
            assert session.session_id in output
            
            # Verify session is terminal
            assert session.is_terminal()
            assert session.end_reason == category
            
        finally:
            sys.stdout = old_stdout
    
    def test_error_handling_no_crash(self):
        """Test that error handling never crashes (CP-04 §3)."""
        # Even with weird errors, should not crash
        weird_errors = [
            Exception(""),
            Exception(None),
            Exception(12345),
            ValueError("Different error type"),
            KeyError("key"),
        ]
        
        session_manager = SessionManager()
        session = session_manager.create_session(direction="inbound")
        
        for error in weird_errors:
            # Should not raise exception
            category = ProviderErrorHandler.handle_error(
                session_id=session.session_id,
                error=error,
                direction="inbound",
            )
            
            # Should always return a category
            assert category is not None
            assert category.startswith("provider.") or category.startswith("call.")
    
    def test_error_handling_redaction(self):
        """Test that secrets are redacted in error details (CP-04 §4)."""
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            session_manager = SessionManager()
            session = session_manager.create_session(direction="inbound")
            
            # Error with potential secret
            error = Exception("Error: API secret abc123xyz leaked")
            ProviderErrorHandler.handle_error(
                session_id=session.session_id,
                error=error,
                direction="inbound",
            )
            
            output = captured_output.getvalue()
            # Should not contain raw secret
            assert "abc123xyz" not in output
            # Should contain redaction indicator
            assert "redacted" in output.lower() or "secret" not in output.lower()
            
        finally:
            sys.stdout = old_stdout
    
    def test_all_categories_map_to_terminal_state(self):
        """Test that each category maps to terminal call.ended (CP-04 §6)."""
        categories = [
            ProviderErrorCategory.AUTH_FAILED,
            ProviderErrorCategory.MISCONFIGURED,
            ProviderErrorCategory.NETWORK_ERROR,
            ProviderErrorCategory.BUSY,
            ProviderErrorCategory.NO_ANSWER,
            ProviderErrorCategory.REJECTED,
            ProviderErrorCategory.FAILED,
            ProviderErrorCategory.RATE_LIMITED,
            ProviderErrorCategory.CAPACITY_LIMITED,
            ProviderErrorCategory.UNKNOWN_ERROR,
        ]
        
        session_manager = SessionManager()
        
        for category in categories:
            session = session_manager.create_session(direction="inbound")
            
            # Handle error
            error = Exception(f"Test error for {category}")
            result_category = ProviderErrorHandler.handle_error(
                session_id=session.session_id,
                error=error,
                direction="inbound",
            )
            
            # End session with category as reason
            session.end(reason=result_category)
            
            # Verify terminal state
            assert session.is_terminal()
            assert session.state == SessionState.ENDED
            assert session.end_reason == result_category


class TestUserMessages:
    """Test user-facing messages per CP-04 §5."""
    
    def test_user_messages_dutch(self):
        """Test that user messages are in Dutch."""
        messages = {
            ProviderErrorCategory.BUSY: ProviderErrorHandler.get_user_message(
                ProviderErrorCategory.BUSY
            ),
            ProviderErrorCategory.NO_ANSWER: ProviderErrorHandler.get_user_message(
                ProviderErrorCategory.NO_ANSWER
            ),
            ProviderErrorCategory.RATE_LIMITED: ProviderErrorHandler.get_user_message(
                ProviderErrorCategory.RATE_LIMITED
            ),
        }
        
        # Check messages are in Dutch (simple heuristic)
        for category, message in messages.items():
            assert len(message) > 0
            # Should contain Dutch words
            assert any(word in message.lower() for word in ["het", "de", "een", "is", "niet"])
    
    def test_user_messages_non_technical(self):
        """Test that messages are non-technical."""
        message = ProviderErrorHandler.get_user_message(ProviderErrorCategory.AUTH_FAILED)
        
        # Should not contain technical terms
        assert "401" not in message
        assert "auth" not in message.lower()
        assert "error" not in message.lower()
        assert "exception" not in message.lower()

