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
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    # Read raw body for signature verification
    body = await request.body()
    
    # Handle webhook
    try:
        result = webhook_handler.handle_webhook(body, authorization)
        
        if result and "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        # Don't crash - log and return error
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

