import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Path, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from conversation_manager import conversation_manager
from llm_router import get_llm_client
from auth import verify_api_key  # 如果未拆 auth，请用原来的 token 验证函数

router = APIRouter()

# ========== 请求模型 ==========
class AddMessageRequest(BaseModel):
    role: str
    content: str
    model: str = "ChatGPT-4o-Latest"
    stream: bool = False

# ========== 接口实现 ==========

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
        if request.stream:
            return await create_conversation_stream_response(
                conversation_id,
                request.role,
                request.content,
                request.model
            )

        # 非流式回复逻辑
        conversation_manager.append_message(conversation_id, request.role, request.content)
        messages = conversation_manager.get_messages(conversation_id)
        chat_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]
        response_content = await llm_client.get_response_complete(chat_messages, request.model)
        conversation_manager.append_message(conversation_id, "assistant", response_content)
        return {
            "conversation_id": conversation_id,
            "reply": response_content
        }

    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def create_conversation_stream_response(conversation_id, user_role, user_content, model):
    llm_client, backend = get_llm_client()
    now = datetime.now()

    # 1. 先追加user消息
    conversation_manager.append_message(conversation_id, user_role, user_content)

    # 2. 获取历史
    messages = conversation_manager.get_messages(conversation_id)
    chat_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
    ]

    # 3. 插入assistant占位符，获得新消息ID
    assistant_msg_id = conversation_manager.insert_assistant_placeholder(conversation_id, created_at=now)

    full_response = ""

    async def generate():
        nonlocal full_response
        try:
            async for chunk in llm_client.get_response_stream(chat_messages, model):
                if chunk:
                    full_response += chunk
                    # **每次流式新内容都及时 update 数据库**
                    conversation_manager.update_message_content_and_time(
                        assistant_msg_id,
                        full_response,
                        created_at=now
                    )
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            # 最后一次确保数据库完整内容
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
    llm_client, backend = get_llm_client()

    # 以“请求到达时间”作为占位消息和后续内容的 created_at
    now = datetime.now()

    # 1. 先追加user消息
    conversation_manager.append_message(conversation_id, user_role, user_content)

    # 2. 获取历史
    messages = conversation_manager.get_messages(conversation_id)
    chat_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
    ]

    # 3. 插入assistant占位符，获得新消息ID
    assistant_msg_id = conversation_manager.insert_assistant_placeholder(conversation_id, created_at=now)

    # 4. 用于累加回复内容
    full_response = ""

    async def generate():
        nonlocal full_response
        try:
            async for chunk in llm_client.get_response_stream(chat_messages, model):
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield f"data: {json.dumps({'content': '', 'finish_reason': 'stop'})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    async def update_assistant_message():
        nonlocal full_response
        async for _ in llm_client.get_response_stream(chat_messages, model):
            pass
        # 生成结束，更新消息内容和最终时间戳
        conversation_manager.update_message_content_and_time(
            assistant_msg_id,
            full_response,
            created_at=now  # 可根据需要用 now，也可用 datetime.now()
        )

    # 并发异步任务，等待流式推送完成后落库
    asyncio.create_task(update_assistant_message())

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )