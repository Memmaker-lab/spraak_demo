"""
OBS-00 event store for querying events by session_id.

In-memory implementation for now (demo/prototype).
Production would use a persistent store (DB, log aggregator, etc.).
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class StoredEvent:
    """An OBS-00 event stored in memory."""
    
    ts: datetime
    session_id: str
    component: str
    event_type: str
    severity: str
    correlation_id: str
    pii: Dict[str, Any]
    payload: Dict[str, Any]  # All other event fields
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to OBS-00 event dict."""
        result = {
            "ts": self.ts.isoformat(),
            "session_id": self.session_id,
            "component": self.component,
            "event_type": self.event_type,
            "severity": self.severity,
            "correlation_id": self.correlation_id,
            "pii": self.pii,
        }
        result.update(self.payload)
        return result


class EventStore:
    """
    In-memory event store for OBS-00 events.
    
    Stores events in a bounded deque (FIFO) to prevent unbounded memory growth.
    Default max size: 10,000 events (configurable).
    """
    
    def __init__(self, max_events: int = 10000):
        self._events: deque[StoredEvent] = deque(maxlen=max_events)
        self._max_events = max_events
    
    def store(self, event: Dict[str, Any]) -> None:
        """
        Store an OBS-00 event.
        
        Args:
            event: OBS-00 event dict (must have ts, session_id, component, event_type, severity, correlation_id, pii)
        """
        # Extract required fields
        ts_str = event.get("ts")
        if isinstance(ts_str, str):
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        else:
            ts = datetime.utcnow()
        
        session_id = event.get("session_id", "")
        component = event.get("component", "unknown")
        event_type = event.get("event_type", "unknown")
        severity = event.get("severity", "info")
        correlation_id = event.get("correlation_id", session_id)
        pii = event.get("pii", {"contains_pii": False, "fields": [], "handling": "none"})
        
        # All other fields go into payload
        payload = {k: v for k, v in event.items() 
                  if k not in ("ts", "session_id", "component", "event_type", "severity", "correlation_id", "pii")}
        
        stored = StoredEvent(
            ts=ts,
            session_id=session_id,
            component=component,
            event_type=event_type,
            severity=severity,
            correlation_id=correlation_id,
            pii=pii,
            payload=payload,
        )
        
        self._events.append(stored)
    
    def query(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        component: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query events with optional filters.
        
        Args:
            session_id: Filter by session_id
            event_type: Filter by event_type (exact match)
            component: Filter by component
            since: Return events after this timestamp (inclusive)
            until: Return events before this timestamp (inclusive)
            limit: Maximum number of events to return (default: all matching)
        
        Returns:
            List of OBS-00 event dicts, ordered by timestamp (oldest first)
        """
        results: List[StoredEvent] = []
        
        for event in self._events:
            # Apply filters
            if session_id and event.session_id != session_id:
                continue
            if event_type and event.event_type != event_type:
                continue
            if component and event.component != component:
                continue
            if since and event.ts < since:
                continue
            if until and event.ts > until:
                continue
            
            results.append(event)
            
            if limit and len(results) >= limit:
                break
        
        # Return as dicts, ordered by timestamp
        return [e.to_dict() for e in results]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        return {
            "total_events": len(self._events),
            "max_events": self._max_events,
            "oldest_event_ts": self._events[0].ts.isoformat() if self._events else None,
            "newest_event_ts": self._events[-1].ts.isoformat() if self._events else None,
        }


# Global event store instance
event_store = EventStore()

