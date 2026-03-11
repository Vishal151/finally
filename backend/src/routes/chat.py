"""Chat API route — wired to LLM module for AI assistant."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..database import queries
from ..llm import handle_chat_message

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    """Send a message to the AI assistant."""
    market_data = request.app.state.market_data
    result = handle_chat_message(body.message, market_data._cache)
    return result


@router.get("/api/chat/history")
async def chat_history():
    """Return chat message history."""
    messages = queries.get_chat_history()
    return {"messages": messages}
