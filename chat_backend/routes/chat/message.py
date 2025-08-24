import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Path, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
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
from db import get_conn

router = APIRouter()


class AddMessageRequest(BaseModel):
    role: str
    content: str
    model: str = "ChatGPT-4o-Latest"
    stream: bool = False
    documents: Optional[List[int]] = Field(default=None, description="plan_documents.id 列表")

    @field_validator("documents")
    @classmethod
    def validate_documents(cls, v):
        if v is None:
            return v
        cleaned: List[int] = []
        for x in v:
            try:
                xi = int(x)
                if xi > 0 and xi not in cleaned:
                    cleaned.append(xi)
            except Exception:
                continue
        return cleaned or None


def _build_kb_block_from_documents(doc_ids: List[int]) -> Optional[str]:
    """
    构建知识库块，格式如下：
    ----- {filename} BEGINE -----
    {content}
    ----- {filename} END -----
    多个文档以空行分隔。
    """
    if not doc_ids:
        return None
    placeholders = ",".join(["%s"] * len(doc_ids))
    # 使用 FIELD 保持顺序与传入一致
    sql = f"""
        SELECT id, filename, content
        FROM plan_documents
        WHERE id IN ({placeholders})
        ORDER BY FIELD(id, {placeholders})
    """
    params = tuple(doc_ids + doc_ids)
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                return None
            columns = [c[0] for c in cursor.description]
            parts: List[str] = []
            for row in rows:
                rec = dict(zip(columns, row))
                filename = (rec.get("filename") or "").strip() or f"document_{rec.get('id')}"
                content = rec.get("content") or ""
                parts.append(f"----- {filename} BEGINE -----\n{content}\n----- {filename} END -----")
            return "\n\n".join(parts) if parts else None


def _inject_kb_into_system_prompt(conversation_id: str, kb_block: Optional[str]) -> Optional[str]:
    """
    将知识库内容追加到 conversations.system_prompt 后面（换行分隔），
    返回合并后的 system prompt（仅用于本次上下文，不修改数据库内容）。
    """
    convo = conversation_manager.get_conversation_by_id(conversation_id)
    original = (convo.get("system_prompt") or "").strip()
    if not kb_block:
        return original or None
    if original:
        return f"{original}\n\n{kb_block}"
    return kb_block


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
    - 新增：可选 documents 入参（plan_documents.id 数组）。若提供，将查询对应 filename 和 content，
      以指定格式拼装为“知识库”并在提交 LLM 前将其内容行换追加到 system prompt。
    - 非流式：直接返回reply与消息ID；会自动更新会话的 updated_at。
    - 流式：SSE输出，第一帧包含user_message_id和assistant_message_id等。
    """
    llm_client, backend = get_llm_client()
    try:
        kb_block: Optional[str] = None
        if request.documents:
            kb_block = _build_kb_block_from_documents(request.documents)

        if request.stream:
            return await create_conversation_stream_response(
                conversation_id,
                user_role=request.role,
                user_content=request.content,
                model=request.model,
                fastapi_request=fastapi_request,
                kb_block=kb_block,
            )

        ignore_user = is_ignored_user_message(request.role, request.content)
        user_message_id = None
        if not ignore_user:
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

        if kb_block:
            injected_system = _inject_kb_into_system_prompt(conversation_id, kb_block)
            if injected_system:
                chat_messages = [{"role": "system", "content": injected_system}] + chat_messages

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
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")
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
    kb_block: Optional[str] = None,
):
    """
    SSE流式回复：
    - 第一帧返回 { user_message_id, assistant_message_id, conversation_id, session_id }
    - 中间多帧返回 { content: "..." }
    - 完成帧 { content: "", finish_reason: "stop" } + [DONE]
    - 如传入 kb_block，则在提交 LLM 前注入到 system prompt
    """
    llm_client, backend = get_llm_client()
    now = datetime.now()

    ignore_user = is_ignored_user_message(user_role, user_content)
    user_message_id = None
    if not ignore_user:
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

    if kb_block:
        injected_system = _inject_kb_into_system_prompt(conversation_id, kb_block)
        if injected_system:
            chat_messages = [{"role": "system", "content": injected_system}] + chat_messages

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