"""
OBS-00: Structured JSON event emission (shared).

This module is shared by Control Plane and Voice Pipeline.
It implements the OBS-00 event envelope and minimal taxonomy helpers.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


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

        json.dump(event, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()


