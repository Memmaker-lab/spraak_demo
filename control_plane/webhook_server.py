"""
Webhook server for receiving LiveKit webhook events.
Can be run standalone or integrated into existing web server.
"""
import json
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

from .webhook_handler import webhook_handler
from .config import config

app = FastAPI(title="Control Plane Webhook Server")


@app.post("/webhook")
async def handle_webhook(
    request: Request,
    authorization: str = Header(None, alias="Authorization"),
):
    """
    LiveKit webhook endpoint.
    Receives webhook events and processes them.
    """
    import sys
    import json as json_lib
    from datetime import datetime, timezone
    
    # Debug: log incoming request
    debug_event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "component": "control_plane",
        "event_type": "webhook.received",
        "severity": "debug",
        "has_auth": authorization is not None,
    }
    json_lib.dump(debug_event, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    
    if not authorization:
        # Log missing auth
        debug_event["event_type"] = "webhook.error"
        debug_event["severity"] = "warn"
        debug_event["error"] = "Missing Authorization header"
        json_lib.dump(debug_event, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    # Read raw body for signature verification
    body = await request.body()
    
    # Debug: log body size
    debug_event["event_type"] = "webhook.processing"
    debug_event["body_size"] = len(body)
    try:
        body_json = json_lib.loads(body)
        debug_event["event"] = body_json.get("event")
        debug_event["room"] = body_json.get("room", {}).get("name") if body_json.get("room") else None
    except:
        pass
    json_lib.dump(debug_event, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    
    # Handle webhook
    try:
        result = webhook_handler.handle_webhook(body, authorization)
        
        if result and "error" in result:
            debug_event["event_type"] = "webhook.error"
            debug_event["severity"] = "error"
            debug_event["error"] = result["error"]
            json_lib.dump(debug_event, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
            sys.stdout.flush()
            raise HTTPException(status_code=400, detail=result["error"])
        
        debug_event["event_type"] = "webhook.processed"
        debug_event["severity"] = "info"
        json_lib.dump(debug_event, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
        
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        # Don't crash - log and return error
        debug_event["event_type"] = "webhook.exception"
        debug_event["severity"] = "error"
        debug_event["error"] = str(e)
        json_lib.dump(debug_event, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stdout.flush()
        
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "component": "control_plane"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

