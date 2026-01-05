"""
Test script om webhook te testen zonder LiveKit.
"""
import json
import sys
from webhook_handler import webhook_handler

# Simuleer een room_started event
test_event = {
    "event": "room_started",
    "id": "test-event-123",
    "createdAt": 1704456000,
    "room": {
        "name": "test-room-123",
        "sid": "RM_test123",
    }
}

print("Testing webhook handler with room_started event...", file=sys.stderr)
print("=" * 60, file=sys.stderr)

body = json.dumps(test_event).encode()
auth_header = "Bearer test-token"

result = webhook_handler.handle_webhook(body, auth_header)
print(f"\nResult: {result}", file=sys.stderr)

