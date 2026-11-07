from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import json
import logging

from app.services.chat_service import chat_service
from app.core.session_manager import get_session_manager
from app.core.config import settings

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)

class ChatSendRequest(BaseModel):
    session_id: str
    message: str
    layer: str = "offline"
    mode: str = "auto"
    model: str = settings.LLM_DEFAULT_MODEL  # Default from .env
    client_context: Optional[Dict[str, Any]] = None

@router.post("/send")
async def send_message(req: ChatSendRequest):
    """
    Send a message to the agent. Returns a Server-Sent Events (SSE) stream.
    """
    async def event_generator():
        try:
            async for event in chat_service.process_message(
                session_id=req.session_id,
                user_message=req.message,
                layer=req.layer,
                mode=req.mode,
                model=req.model,
                client_context=req.client_context
            ):
                # Format as SSE
                # data: {json}\n\n
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Stream Error: {e}")
            err_event = {"type": "error", "content": "Internal Stream Error"}
            yield f"data: {json.dumps(err_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """
    Get chat history for a session.
    """
    mgr = get_session_manager()
    history = await mgr.get_chat_history(session_id, limit=50)
    return {
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "source": m.source,
                "created_at": m.created_at
            }
            for m in history
        ]
    }
