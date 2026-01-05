"""
Tests for logging_setup module.

Verifies:
- JSON structured logging format
- Component and severity tagging
- Session ID correlation
- PII-aware logging helpers
- Log level configuration
"""
import json
import logging
from io import StringIO
from datetime import datetime

import pytest

from logging_setup import (
    setup_logging,
    get_logger,
    Component,
    Severity,
    JSONFormatter,
    StructuredLogger,
)


@pytest.fixture
def capture_logs():
    """Capture log output to a string buffer."""
    buffer = StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JSONFormatter())
    
    logger = logging.getLogger()
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    yield buffer
    
    logger.handlers = []


def test_json_formatter_basic(capture_logs):
    """Test basic JSON log formatting."""
    logger = get_logger(Component.CONTROL_PLANE)
    logger.info("Test message", extra_field="value")
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    assert log_entry["severity"] == "info"
    assert log_entry["component"] == "control_plane"
    assert log_entry["message"] == "Test message"
    assert log_entry["extra_field"] == "value"
    assert "timestamp" in log_entry


def test_json_formatter_timestamp_format(capture_logs):
    """Test that timestamp is in ISO8601 format."""
    logger = get_logger(Component.VOICE_PIPELINE)
    logger.info("Timestamp test")
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    # Should be parseable as ISO8601
    timestamp = log_entry["timestamp"]
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert dt is not None


def test_session_id_correlation(capture_logs):
    """Test that session_id is included when provided."""
    logger = get_logger(Component.CONTROL_PLANE, session_id="sess_123")
    logger.info("Session test")
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    assert log_entry["session_id"] == "sess_123"


def test_session_id_absent_when_not_provided(capture_logs):
    """Test that session_id is absent when not provided."""
    logger = get_logger(Component.VOICE_PIPELINE)
    logger.info("No session")
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    assert "session_id" not in log_entry


def test_with_session_creates_new_logger(capture_logs):
    """Test that with_session creates a new logger with session ID."""
    base_logger = get_logger(Component.CONTROL_PLANE)
    session_logger = base_logger.with_session("sess_456")
    
    session_logger.info("With session")
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    assert log_entry["session_id"] == "sess_456"


def test_pii_logging(capture_logs):
    """Test that PII is logged in a separate field."""
    logger = get_logger(Component.CONTROL_PLANE, session_id="sess_789")
    logger.info_pii("User contacted", phone="+31612345678", name="John Doe")
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    assert "pii" in log_entry
    assert log_entry["pii"]["phone"] == "+31612345678"
    assert log_entry["pii"]["name"] == "John Doe"
    assert log_entry["message"] == "User contacted"


def test_severity_levels(capture_logs):
    """Test all severity levels."""
    logger = get_logger(Component.VOICE_PIPELINE)
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")
    
    output = capture_logs.getvalue()
    lines = [line for line in output.strip().split("\n") if line]
    
    assert len(lines) == 5
    
    severities = [json.loads(line)["severity"] for line in lines]
    assert severities == ["debug", "info", "warning", "error", "critical"]


def test_component_enum():
    """Test that Component enum has expected values."""
    assert Component.CONTROL_PLANE.value == "control_plane"
    assert Component.VOICE_PIPELINE.value == "voice_pipeline"
    assert Component.STT.value == "stt"
    assert Component.LLM.value == "llm"
    assert Component.TTS.value == "tts"


def test_component_string_fallback(capture_logs):
    """Test that component can be a plain string."""
    logger = get_logger("custom_component")
    logger.info("Test")
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    assert log_entry["component"] == "custom_component"


def test_multiple_extra_fields(capture_logs):
    """Test logging with multiple extra fields."""
    logger = get_logger(Component.CONTROL_PLANE)
    logger.info(
        "Complex log",
        field1="value1",
        field2=123,
        field3=True,
        field4={"nested": "object"}
    )
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    assert log_entry["field1"] == "value1"
    assert log_entry["field2"] == 123
    assert log_entry["field3"] is True
    assert log_entry["field4"] == {"nested": "object"}


def test_setup_logging_json():
    """Test setup_logging with JSON format."""
    setup_logging(level="DEBUG", use_json=True)
    
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 1
    assert isinstance(root_logger.handlers[0].formatter, JSONFormatter)


def test_setup_logging_text():
    """Test setup_logging with text format."""
    setup_logging(level="INFO", use_json=False)
    
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) == 1
    assert not isinstance(root_logger.handlers[0].formatter, JSONFormatter)


def test_exception_logging(capture_logs):
    """Test that exceptions are logged properly."""
    logger = get_logger(Component.ERROR_HANDLER)
    
    try:
        raise ValueError("Test exception")
    except Exception as e:
        logger.error("Exception occurred", exc_info=True)
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    assert "exception" in log_entry
    assert "ValueError: Test exception" in log_entry["exception"]


def test_debug_pii_method(capture_logs):
    """Test debug_pii convenience method."""
    logger = get_logger(Component.CONTROL_PLANE)
    logger.debug_pii("Debug with PII", email="test@example.com")
    
    output = capture_logs.getvalue()
    log_entry = json.loads(output.strip())
    
    assert log_entry["severity"] == "debug"
    assert log_entry["pii"]["email"] == "test@example.com"

