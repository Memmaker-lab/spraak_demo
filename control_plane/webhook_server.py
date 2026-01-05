"""
Webhook server for receiving LiveKit webhook events.
Can be run standalone or integrated into existing web server.
"""
import json
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

from .webhook_handler import webhook_handler
from .config import config
from logging_setup import get_logger, Component
from .control_api import router as control_router

app = FastAPI(title="Control Plane Webhook Server")
logger = get_logger(Component.WEBHOOK_SERVER)
app.include_router(control_router)


@app.post("/webhook")
async def handle_webhook(
    request: Request,
    authorization: str = Header(None, alias="Authorization"),
):
    """
    LiveKit webhook endpoint.
    Receives webhook events and processes them.
    """
    # Log incoming request
    logger.debug(
        "Webhook received",
        has_auth=authorization is not None
    )
    
    if not authorization:
        logger.warning("Webhook missing Authorization header")
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    # Read raw body for signature verification
    body = await request.body()
    
    # Log webhook details
    try:
        body_json = json.loads(body)
        event = body_json.get("event")
        room = body_json.get("room", {}).get("name") if body_json.get("room") else None
        logger.debug(
            "Processing webhook",
            body_size=len(body),
            event=event,
            room=room
        )
    except json.JSONDecodeError:
        logger.warning("Failed to parse webhook body as JSON", body_size=len(body))
    
    # Handle webhook
    try:
        result = webhook_handler.handle_webhook(body, authorization)
        
        if result and "error" in result:
            logger.error("Webhook processing failed", error=result["error"])
            raise HTTPException(status_code=400, detail=result["error"])
        
        logger.info("Webhook processed successfully")
        return JSONResponse(content={"status": "ok"})
    except HTTPException:
        raise
    except Exception as e:
        # Don't crash - log and return error
        logger.error("Webhook processing exception", error=str(e), exception_type=type(e).__name__)
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

