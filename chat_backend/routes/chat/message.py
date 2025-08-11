import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Path, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from conversation_manager import conversation_manager
from llm_router import get_llm_client
from auth import verify_api_key
from services.message_utils import (
    is_ignored_user_message,
    merge_assistant_messages_with_user_history,
)
from services.chat_stream import (
    StreamSession,
    get_session,
    add_session,
    remove_session,
)
router = APIRouter()
class AddMessageRequest(BaseModel):
    role: str
    content: str
    model: str = "ChatGPT-4o-Latest"
    stream: bool = False
@router.get("/v1/chat/conversations/{conversation_id}/messages")
async def get_conversation_history(conversation_id: str = Path(...)):
    """
    返回指定会话的消息列表，包含：
    - id, role, content, created_at, updated_at
    """
    try:
        messages = conversation_manager.get_messages(conversation_id)
        return {"conversation_id": conversation_id, "messages": messages}
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")
@router.post("/v1/chat/conversations/{conversation_id}/messages")
async def add_message_and_reply(
    conversation_id: str = Path(...),
    request: AddMessageRequest = Body(...),
    api_key: str = Depends(verify_api_key),
    fastapi_request: Request = None,
):
    """
    新增用户消息并获取助手回复。
    - 非流式：直接返回reply与消息ID；会自动更新会话的 updated_at。
    - 流式：SSE输出，第一帧包含user_message_id和assistant_message_id等。
    """
    llm_client, backend = get_llm_client()
    try:
        if request.stream:
            return await create_conversation_stream_response(
                conversation_id,
                user_role=request.role,
                user_content=request.content,
                model=request.model,
                fastapi_request=fastapi_request,
            )
        ignore_user = is_ignored_user_message(request.role, request.content)
        user_message_id = None
        if not ignore_user:
            # 会自动更新 conversations.updated_at
            user_message_id = conversation_manager.append_message(
                conversation_id, request.role, request.content
            )
        messages = conversation_manager.get_messages(conversation_id)
        chat_messages = merge_assistant_messages_with_user_history(
            messages,
            user_role=request.role,
            user_content=request.content,
            ignore_user=ignore_user,
        )
        response_content = await llm_client.get_response_complete(
            chat_messages, request.model
        )
        assistant_message_id = conversation_manager.append_message(
            conversation_id, "assistant", response_content
        )
        return {
            "conversation_id": conversation_id,
            "reply": response_content,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
async def create_conversation_stream_response(
    conversation_id: str,
    user_role: str,
    user_content: str,
    model: str,
    fastapi_request: Request = None,
):
    """
    SSE流式回复：
    - 第一帧返回 { user_message_id, assistant_message_id, conversation_id, session_id }
    - 中间多帧返回 { content: "..." }
    - 完成帧 { content: "", finish_reason: "stop" } + [DONE]
    """
    llm_client, backend = get_llm_client()
    now = datetime.now()
    ignore_user = is_ignored_user_message(user_role, user_content)
    user_message_id = None
    if not ignore_user:
        # append_message 内部自动更新 conversations.updated_at
        user_message_id = conversation_manager.append_message(
            conversation_id, user_role, user_content
        )
    messages = conversation_manager.get_messages(conversation_id)
    chat_messages = merge_assistant_messages_with_user_history(
        messages,
        user_role=user_role,
        user_content=user_content,
        ignore_user=ignore_user,
    )
    # 占位符插入也会更新会话 updated_at
    assistant_msg_id = conversation_manager.insert_assistant_placeholder(
        conversation_id, created_at=now
    )
    session_id = f"{conversation_id}:{assistant_msg_id}:{int(now.timestamp() * 1000)}"
    session = StreamSession(
        session_id=session_id,
        llm_client=llm_client,
        chat_messages=chat_messages,
        model=model,
        assistant_msg_id=assistant_msg_id,
        now=now,
    )
    add_session(session_id, session)
    session.start()
    async def generate():
        # 首帧：元信息
        yield f"data: {json.dumps({'user_message_id': user_message_id, 'assistant_message_id': assistant_msg_id, 'conversation_id': conversation_id, 'session_id': session_id})}\n\n"
        sent_idx = 0
        try:
            while not session.is_completed() or sent_idx < len(session.chunks):
                req: Request = fastapi_request
                if req is not None and hasattr(req, "is_disconnected"):
                    if await req.is_disconnected():
                        break
                new_chunks = session.get_chunks(sent_idx)
                for chunk in new_chunks:
                    sent_idx += 1
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                await asyncio.sleep(0.15)
            if session.exception:
                yield f"data: {json.dumps({'error': str(session.exception)})}\n\n"
            else:
                yield f"data: {json.dumps({'content': '', 'finish_reason': 'stop'})}\n\n"
                yield "data: [DONE]\n\n"
        finally:
            remove_session(session_id)
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )
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