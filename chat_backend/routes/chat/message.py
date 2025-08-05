import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Path, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from conversation_manager import conversation_manager
from llm_router import get_llm_client
from auth import verify_api_key
from config import Config
from typing import List

router = APIRouter()

class AddMessageRequest(BaseModel):
    role: str
    content: str
    model: str = "ChatGPT-4o-Latest"
    stream: bool = False  # 前端可传 stream: true

def is_ignored_user_message(role: str, content: str) -> bool:
    """
    判断用户消息是否在忽略列表。先对 content 做 strip，再完全匹配。
    """
    if role.lower() == "user":
        trimmed = content.strip()
        return trimmed in [msg.strip() for msg in Config.ignoredUserMessages]
    return False

def merge_assistant_messages_with_user_history(messages, user_role=None, user_content=None, ignore_user=False):
    """
    使消息序列始终成 user/assistant/user/assistant... 结构，合并连续 assistant 消息
    若 ignore_user=True，则 user_role 和 user_content 为当前未入库但要发送的 user 消息
    返回格式为仅包含 role 和 content 的消息列表（用于发送给LLM）
    """
    result = []
    temp_assistant = []

    # 补充当前用户消息
    if ignore_user and user_role and user_content:
        in_msgs = messages + [{"role": user_role, "content": user_content}]
    else:
        in_msgs = messages

    for msg in in_msgs:
        role = msg["role"]
        content = msg["content"]
        if role == "assistant":
            temp_assistant.append(content)
        else:
            # 遇到 user，若有累计的 assistant，则合并加入
            if temp_assistant:
                merged = "\n---\n".join(temp_assistant)
                result.append({"role": "assistant", "content": merged})
                temp_assistant = []
            result.append({"role": role, "content": content})
    # 最后如果结尾还有 assistant 也要合并
    if temp_assistant:
        merged = "\n---\n".join(temp_assistant)
        result.append({"role": "assistant", "content": merged})
    return result

@router.get("/v1/chat/conversations/{conversation_id}/messages")
async def get_conversation_history(conversation_id: str = Path(...)):
    try:
        messages = conversation_manager.get_messages(conversation_id)
        return {"conversation_id": conversation_id, "messages": messages}
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")

@router.post("/v1/chat/conversations/{conversation_id}/messages")
async def add_message_and_reply(
    conversation_id: str = Path(...),
    request: AddMessageRequest = Body(...),
    api_key: str = Depends(verify_api_key)
):
    llm_client, backend = get_llm_client()
    try:
        # ===== 新增：支持流式返回 =====
        if request.stream:
            return await create_conversation_stream_response(
                conversation_id,
                user_role=request.role,
                user_content=request.content,
                model=request.model
            )
        # ===== 同步返回（原逻辑） =====
        print(f"[DEBUG] conversation_id={conversation_id}, request={request}")
        ignore_user = is_ignored_user_message(request.role, request.content)
        user_message_id = None
        if not ignore_user:
            user_message_id = conversation_manager.append_message(conversation_id, request.role, request.content)
        
        messages = conversation_manager.get_messages(conversation_id)
        print(f"[DEBUG] messages={messages}")
        chat_messages = merge_assistant_messages_with_user_history(
            messages,
            user_role=request.role,
            user_content=request.content,
            ignore_user=ignore_user
        )
        print(f"[DEBUG] chat_messages={chat_messages}")
        response_content = await llm_client.get_response_complete(chat_messages, request.model)
        assistant_message_id = conversation_manager.append_message(conversation_id, "assistant", response_content)
        
        return {
            "conversation_id": conversation_id,
            "reply": response_content,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def create_conversation_stream_response(conversation_id, user_role, user_content, model):
    llm_client, backend = get_llm_client()
    now = datetime.now()

    ignore_user = is_ignored_user_message(user_role, user_content)

    user_message_id = None
    if not ignore_user:
        user_message_id = conversation_manager.append_message(conversation_id, user_role, user_content)

    messages = conversation_manager.get_messages(conversation_id)

    chat_messages = merge_assistant_messages_with_user_history(
        messages,
        user_role=user_role,
        user_content=user_content,
        ignore_user=ignore_user
    )

    assistant_msg_id = conversation_manager.insert_assistant_placeholder(conversation_id, created_at=now)

    full_response = ""

    async def generate():
        nonlocal full_response
        try:
            # 首先发送消息ID信息
            yield f"data: {json.dumps({'user_message_id': user_message_id, 'assistant_message_id': assistant_msg_id, 'conversation_id': conversation_id})}\n\n"
            
            async for chunk in llm_client.get_response_stream(chat_messages, model):
                if chunk:
                    full_response += chunk
                    conversation_manager.update_message_content_and_time(
                        assistant_msg_id,
                        full_response,
                        created_at=now
                    )
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            conversation_manager.update_message_content_and_time(
                assistant_msg_id,
                full_response,
                created_at=now
            )
            yield f"data: {json.dumps({'content': '', 'finish_reason': 'stop'})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
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