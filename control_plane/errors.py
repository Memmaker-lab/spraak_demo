"""
CP-04: Telephony provider error handling.
Maps provider errors to stable categories without crashing.
"""
from typing import Optional
from .events import control_plane_emitter, Severity


class ProviderErrorCategory:
    """Stable error categories per CP-04."""
    
    # Call setup / routing
    AUTH_FAILED = "provider.auth_failed"
    MISCONFIGURED = "provider.misconfigured"
    NETWORK_ERROR = "provider.network_error"
    
    # Call outcome
    BUSY = "call.busy"
    NO_ANSWER = "call.no_answer"
    REJECTED = "call.rejected"
    FAILED = "call.failed"
    
    # Limits / throttling
    RATE_LIMITED = "provider.rate_limited"
    CAPACITY_LIMITED = "provider.capacity_limited"
    
    # Unknown
    UNKNOWN_ERROR = "provider.unknown_error"


class ProviderErrorHandler:
    """Handles provider errors per CP-04."""
    
    @staticmethod
    def classify_error(
        error: Exception,
        provider_name: Optional[str] = None,
    ) -> str:
        """
        Classify provider error into stable category per CP-04.
        Returns error category string.
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Check for specific error patterns
        if "auth" in error_str or "unauthorized" in error_str or "401" in error_str:
            return ProviderErrorCategory.AUTH_FAILED
        
        if "config" in error_str or "misconfigured" in error_str:
            return ProviderErrorCategory.MISCONFIGURED
        
        if "network" in error_str or "timeout" in error_str or "connection" in error_str:
            return ProviderErrorCategory.NETWORK_ERROR
        
        if "busy" in error_str or "486" in error_str:
            return ProviderErrorCategory.BUSY
        
        if "no answer" in error_str or "noanswer" in error_str or "480" in error_str:
            return ProviderErrorCategory.NO_ANSWER
        
        if "rejected" in error_str or "reject" in error_str or "603" in error_str:
            return ProviderErrorCategory.REJECTED
        
        if "rate limit" in error_str or "429" in error_str or "throttle" in error_str:
            return ProviderErrorCategory.RATE_LIMITED
        
        if "capacity" in error_str or "503" in error_str:
            return ProviderErrorCategory.CAPACITY_LIMITED
        
        # Default to unknown
        return ProviderErrorCategory.UNKNOWN_ERROR
    
    @staticmethod
    def handle_error(
        session_id: str,
        error: Exception,
        direction: str,
        provider_name: Optional[str] = None,
        livekit_room: Optional[str] = None,
        livekit_participant: Optional[str] = None,
    ) -> str:
        """
        Handle provider error per CP-04.
        Emits events and returns error category.
        Does NOT crash - always returns a category.
        """
        category = ProviderErrorHandler.classify_error(error, provider_name)
        
        # Get error detail (redacted - no secrets)
        detail = str(error)
        # Remove potential secrets (simple heuristic)
        if "secret" in detail.lower() or "password" in detail.lower() or "key" in detail.lower():
            detail = "[redacted: potential secret]"
        
        # Emit provider event
        control_plane_emitter.provider_event(
            session_id=session_id,
            category=category,
            direction=direction,
            provider_name=provider_name,
            detail=detail,
            livekit_room=livekit_room,
            livekit_participant=livekit_participant,
        )
        
        return category
    
    @staticmethod
    def get_user_message(category: str) -> str:
        """
        Get user-facing Dutch message per CP-04.
        These are used by voice pipeline UX layer.
        """
        messages = {
            ProviderErrorCategory.BUSY: "Het nummer is in gesprek. Zullen we later nog eens proberen?",
            ProviderErrorCategory.NO_ANSWER: "Er wordt niet opgenomen. Wil je het later opnieuw proberen?",
            ProviderErrorCategory.RATE_LIMITED: "Momentje, het is even druk. Probeer het zo nog eens.",
            ProviderErrorCategory.CAPACITY_LIMITED: "Momentje, het is even druk. Probeer het zo nog eens.",
            ProviderErrorCategory.AUTH_FAILED: "Sorry, het lukt nu even niet.",
            ProviderErrorCategory.MISCONFIGURED: "Sorry, het lukt nu even niet.",
        }
        
        return messages.get(category, "Sorry, het lukt nu even niet.")

