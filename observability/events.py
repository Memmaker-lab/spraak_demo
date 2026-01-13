"""
OBS-00: Structured JSON event emission (shared).

This module is shared by Control Plane and Voice Pipeline.
It implements the OBS-00 event envelope and minimal taxonomy helpers.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from .event_store import event_store


class Component(str, Enum):
    """Component types per OBS-00."""

    CONTROL_PLANE = "control_plane"
    VOICE_PIPELINE = "voice_pipeline"
    ADAPTER = "adapter"
    ACTION_RUNNER = "action_runner"


class Severity(str, Enum):
    """Event severity levels per OBS-00."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


DEFAULT_PII = {"contains_pii": False, "fields": [], "handling": "none"}


class EventEmitter:
    """Emits structured JSON events per OBS-00."""
    
    # ANSI color codes for latency formatting
    ORANGE = '\033[38;5;208m'  # Bright orange (256-color mode)
    RESET = '\033[0m'

    def __init__(self, component: Component):
        self.component = component

    def emit(
        self,
        event_type: str,
        session_id: str,
        severity: Severity = Severity.INFO,
        correlation_id: Optional[str] = None,
        pii: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "component": self.component.value,
            "event_type": event_type,
            "severity": severity.value,
            "correlation_id": correlation_id or session_id,
            "pii": pii or DEFAULT_PII,
        }

        event.update(kwargs)
        
        # Check if latency_ms is present for color formatting
        latency_ms = kwargs.get("latency_ms")
        
        # Generate JSON output
        json_output = json.dumps(event, ensure_ascii=False)
        
        # Post-process JSON to add "ms" unit and color for latency_ms
        if latency_ms is not None:
            # Check if stdout is a TTY (terminal) for color support
            try:
                is_tty = sys.stdout.isatty()
            except (AttributeError, OSError):
                is_tty = False
            
            # Apply colors by default for console output
            # Can be disabled with NO_COLOR=1 or forced with FORCE_COLOR=1
            force_color = os.environ.get('FORCE_COLOR', '').lower() in ('1', 'true', 'yes')
            no_color = os.environ.get('NO_COLOR', '').lower() in ('1', 'true', 'yes')
            # Default to True (use color) unless NO_COLOR is set or we're definitely not a TTY
            use_color = (is_tty or force_color or True) and not no_color
            
            # Match "latency_ms": <number> (with optional whitespace)
            pattern = r'("latency_ms"\s*:\s*)(\d+)'
            
            if use_color:
                # Replace with orange-colored value + "ms"
                replacement = rf'\1{self.ORANGE}\2 ms{self.RESET}'
            else:
                # Just add "ms" without color
                replacement = r'\1\2 ms'
            
            json_output = re.sub(pattern, replacement, json_output)

        # Emit to stdout (for log aggregation)
        sys.stdout.write(json_output)
        sys.stdout.write("\n")
        sys.stdout.flush()
        
        # Store in event store (for CP-03 read API) - use original event dict (no color formatting)
        event_store.store(event)


