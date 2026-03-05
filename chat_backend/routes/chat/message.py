import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from auth import verify_api_key
from conversation_manager import conversation_manager
from llm_router import get_llm_client
from services.chat_stream import StreamSession, add_session, get_session, remove_session
from services.kb_documents import build_kb_block_from_documents, inject_kb_into_system_prompt
from services.message_utils import is_ignored_user_message, merge_assistant_messages_with_user_history
from services.poe_messages import normalize_messages_for_poe

router = APIRouter()


class AddMessageRequest(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]
    model: str = "ChatGPT-4o-Latest"
    stream: bool = False
    documents: Optional[List[int]] = Field(default=None, description="plan_documents.id list")

    @field_validator("documents")
    @classmethod
    def validate_documents(cls, v):
        if v is None:
            return None
        out: List[int] = []
        for x in v:
            try:
                i = int(x)
                if i > 0 and i not in out:
                    out.append(i)
            except Exception:
                continue
        return out or None


@router.get("/v1/chat/conversations/{conversation_id}/messages")
async def get_conversation_history(conversation_id: str = Path(...)):
    try:
        return {"conversation_id": conversation_id, "messages": conversation_manager.get_messages(conversation_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post("/v1/chat/conversations/{conversation_id}/messages")
async def add_message_and_reply(
    conversation_id: str = Path(...),
    request: AddMessageRequest = Body(...),
    api_key: str = Depends(verify_api_key),
    fastapi_request: Request = None,
):
    llm_client, _ = get_llm_client()
    try:
        kb_block = build_kb_block_from_documents(request.documents or [])
        if request.stream:
            return await _stream_reply(conversation_id, request, fastapi_request, kb_block)

        ignore_user = is_ignored_user_message(request.role, request.content)
        user_message_id = None
        if not ignore_user:
            user_message_id = conversation_manager.append_message(conversation_id, request.role, request.content)

        history = conversation_manager.get_messages(conversation_id)
        chat_messages = merge_assistant_messages_with_user_history(
            history, user_role=request.role, user_content=request.content, ignore_user=ignore_user
        )
        if kb_block:
            sp = inject_kb_into_system_prompt(conversation_id, kb_block)
            if sp:
                chat_messages = [{"role": "system", "content": sp}] + chat_messages

        llm_messages = normalize_messages_for_poe(chat_messages)
        response_content = await llm_client.get_response_complete(llm_messages, request.model)
        assistant_message_id = conversation_manager.append_message(conversation_id, "assistant", response_content)

        return {
            "conversation_id": conversation_id,
            "reply": response_content,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_reply(conversation_id: str, req: AddMessageRequest, fastapi_request: Request, kb_block: Optional[str]):
    llm_client, _ = get_llm_client()
    now = datetime.now()

    ignore_user = is_ignored_user_message(req.role, req.content)
    user_message_id = None
    if not ignore_user:
        user_message_id = conversation_manager.append_message(conversation_id, req.role, req.content)

    history = conversation_manager.get_messages(conversation_id)
    chat_messages = merge_assistant_messages_with_user_history(
        history, user_role=req.role, user_content=req.content, ignore_user=ignore_user
    )
    if kb_block:
        sp = inject_kb_into_system_prompt(conversation_id, kb_block)
        if sp:
            chat_messages = [{"role": "system", "content": sp}] + chat_messages

    session = StreamSession(
        session_id=f"{conversation_id}:{int(now.timestamp() * 1000)}",
        llm_client=llm_client,
        chat_messages=normalize_messages_for_poe(chat_messages),
        model=req.model,
        assistant_msg_id=conversation_manager.insert_assistant_placeholder(conversation_id, created_at=now),
        now=now,
    )
    add_session(session.session_id, session)
    session.start()

    async def generate():
        yield f"data: {json.dumps({'user_message_id': user_message_id, 'assistant_message_id': session.assistant_msg_id, 'conversation_id': conversation_id, 'session_id': session.session_id})}\n\n"
        sent = 0
        try:
            while not session.is_completed() or sent < len(session.chunks):
                if fastapi_request and await fastapi_request.is_disconnected():
                    session.stop()
                    break
                for chunk in session.get_chunks(sent):
                    sent += 1
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                await asyncio.sleep(0.15)
            if session.exception:
                yield f"data: {json.dumps({'error': str(session.exception)})}\n\n"
            else:
                yield f"data: {json.dumps({'content': '', 'finish_reason': 'stop'})}\n\n"
                yield "data: [DONE]\n\n"
        finally:
            remove_session(session.session_id)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


class DeleteMessagesRequest(BaseModel):
    message_ids: List[int]


@router.post("/v1/chat/messages/delete")
async def delete_messages(request: DeleteMessagesRequest = Body(...)):
    try:
        count = conversation_manager.delete_messages(request.message_ids)
        return {"message": f"{count} messages deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class StopStreamRequest(BaseModel):
    session_id: str


@router.post("/v1/chat/stop-stream")
async def stop_stream(request: StopStreamRequest = Body(...)):
    session = get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Stream session not found")
    session.stop()
    session.completed.wait(timeout=3)
    remove_session(request.session_id)
    return {"message": "Stream stopped", "session_id": request.session_id}