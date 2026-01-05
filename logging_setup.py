"""
Shared logging infrastructure for spraak_demo.

This module provides a unified logging setup for both Control Plane and Voice Pipeline,
adhering to OBS-00 structured event principles.

Features:
- JSON-formatted structured logs
- Configurable log levels
- Session ID correlation across all logs
- Component and severity tagging
- PII-aware logging helpers
- Compatible with EventEmitter for OBS-00 events
"""

import json
import logging
import sys
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class Severity(str, Enum):
    """Log severity levels aligned with OBS-00."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Component(str, Enum):
    """System components for log tagging."""
    CONTROL_PLANE = "control_plane"
    VOICE_PIPELINE = "voice_pipeline"
    WEBHOOK_SERVER = "webhook_server"
    SESSION_MANAGER = "session_manager"
    ERROR_HANDLER = "error_handler"
    LIVEKIT_TRANSPORT = "livekit_transport"
    STT = "stt"
    LLM = "llm"
    TTS = "tts"
    VAD = "vad"


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    
    Outputs logs in a format compatible with OBS-00:
    - ISO8601 timestamp
    - Severity level
    - Component identifier
    - Session ID (if available in extra)
    - Message and additional fields
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname.lower(),
            "component": getattr(record, "component", "unknown"),
            "message": record.getMessage(),
        }
        
        # Add session_id if present
        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id
        
        # Add any extra fields from the record
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info",
                "component", "session_id", "message"
            ]:
                log_data[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class StructuredLogger:
    """
    Wrapper around Python's logging with structured JSON output.
    
    Usage:
        logger = StructuredLogger("my_component", session_id="sess_123")
        logger.info("Processing started", extra_field="value")
        logger.error("Failed to process", error="details")
        logger.debug_pii("User data", phone="+31612345678")
    """
    
    def __init__(
        self,
        component: str | Component,
        session_id: Optional[str] = None,
        logger_name: Optional[str] = None
    ):
        self.component = component.value if isinstance(component, Component) else component
        self.session_id = session_id
        self.logger = logging.getLogger(logger_name or self.component)
    
    def _log(
        self,
        level: int,
        message: str,
        pii: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """Internal logging method with structured data."""
        # Extract reserved logging kwargs
        exc_info = kwargs.pop("exc_info", None)
        stack_info = kwargs.pop("stack_info", None)
        stacklevel = kwargs.pop("stacklevel", 1)
        
        extra = {
            "component": self.component,
            **kwargs
        }
        
        if self.session_id:
            extra["session_id"] = self.session_id
        
        if pii:
            # PII is logged as a separate field for audit awareness
            extra["pii"] = pii
        
        self.logger.log(
            level,
            message,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra
        )
    
    def debug(self, message: str, **kwargs):
        """Log a debug message."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log an info message."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log a warning message."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log an error message."""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log a critical message."""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def debug_pii(self, message: str, **pii_fields):
        """
        Log debug with PII fields explicitly marked.
        
        Example:
            logger.debug_pii("User contacted", phone="+31612345678", name="John")
        """
        self._log(logging.DEBUG, message, pii=pii_fields)
    
    def info_pii(self, message: str, **pii_fields):
        """Log info with PII fields explicitly marked."""
        self._log(logging.INFO, message, pii=pii_fields)
    
    def with_session(self, session_id: str) -> "StructuredLogger":
        """Create a new logger instance with a session ID."""
        return StructuredLogger(
            self.component,
            session_id=session_id,
            logger_name=self.logger.name
        )


def setup_logging(
    level: str = "INFO",
    use_json: bool = True,
    include_timestamp: bool = True
) -> None:
    """
    Configure root logger for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Use JSON formatter (True) or simple text (False)
        include_timestamp: Include timestamps in logs
    
    This should be called once at application startup.
    """
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Set formatter
    if use_json:
        formatter = JSONFormatter()
    else:
        format_str = "%(levelname)s - %(component)s - %(message)s"
        if include_timestamp:
            format_str = "%(asctime)s - " + format_str
        formatter = logging.Formatter(format_str)
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)


def get_logger(
    component: str | Component,
    session_id: Optional[str] = None
) -> StructuredLogger:
    """
    Get a structured logger for a component.
    
    Args:
        component: Component name or Component enum
        session_id: Optional session ID for correlation
    
    Returns:
        StructuredLogger instance
    
    Example:
        logger = get_logger(Component.CONTROL_PLANE, session_id="sess_123")
        logger.info("Session started")
    """
    return StructuredLogger(component, session_id=session_id)

