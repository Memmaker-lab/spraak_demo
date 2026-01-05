#!/bin/bash
# Test webhook handmatig

echo "Testing webhook endpoint..."
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{
    "event": "room_started",
    "id": "test-event-123",
    "createdAt": 1704456000,
    "room": {
      "name": "test-room-123",
      "sid": "RM_test123"
    }
  }' \
  -v

echo ""
echo "Check de webhook server terminal voor events."

