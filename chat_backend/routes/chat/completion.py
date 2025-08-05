import uuid
import time
import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import StreamingResponse

from models import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,
    ChatMessage, Role, ChatCompletionUsage,
    ChatCompletionStreamResponse, ChatCompletionStreamChoice
)
from llm_router import get_llm_client
from logger import request_logger
from auth import verify_api_key
from conversation_manager import conversation_manager  # 新增

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/v1/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key)
):
    llm_client, backend = get_llm_client()
    start_time = time.time()

    messages = []
    for msg in request.messages:
        msg_dict = {"role": msg.role.value}
        if msg.content:
            msg_dict["content"] = msg.content
        if msg.function_call:
            msg_dict["function_call"] = msg.function_call.model_dump()
        if msg.tool_calls:
            msg_dict["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
        if msg.name:
            msg_dict["name"] = msg.name
        if msg.tool_call_id:
            msg_dict["tool_call_id"] = msg.tool_call_id
        messages.append(msg_dict)

    try:
        if request.stream:
            # 如果有 conversation_id 字段，则支持多轮对话落库
            conversation_id = None
            # 支持"OpenAI风格"自定义扩展：在 extra 或 messages 中带 conversation_id 字段
            for msg in request.messages:
                if hasattr(msg, "conversation_id"):
                    conversation_id = msg.conversation_id
                    break
                # 也可以约定 name/conversation_id 字段
                if hasattr(msg, "name") and str(msg.name).startswith("cid-"):
                    conversation_id = str(msg.name)[4:]
                    break

            return await _stream_response(
                llm_client, backend, request, messages, start_time, conversation_id=conversation_id
            )
        else:
            response_content = await llm_client.get_response_complete(messages, request.model)
            response = ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex}",
                created=int(time.time()),
                model=request.model,
                choices=[ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role=Role.ASSISTANT, content=response_content),
                    finish_reason="stop"
                )],
                usage=ChatCompletionUsage(
                    prompt_tokens=sum(len(str(msg.get('content', '')).split()) for msg in messages),
                    completion_tokens=len(response_content.split()),
                    total_tokens=sum(len(str(msg.get('content', '')).split()) for msg in messages) + len(response_content.split())
                )
            )
            request_logger.log_request_response(
                request.model_dump(),
                response.model_dump(),
                time.time() - start_time
            )
            return response
    except Exception as e:
        logger.error(f"Error in chat completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _stream_response(
    llm_client, backend, request, messages, start_time, conversation_id=None
):
    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_time = int(time.time())
    full_response = ""
    assistant_msg_id = None
    now = datetime.now()

    # 如果有 conversation_id，可落库
    if conversation_id:
        try:
            # 插入占位符
            assistant_msg_id = conversation_manager.insert_assistant_placeholder(conversation_id, created_at=now)
        except Exception as e:
            logger.warning(f"Insert assistant placeholder failed: {e}")

    async def generate():
        nonlocal full_response
        try:
            async for chunk in llm_client.get_response_stream(messages, request.model):
                if chunk:
                    full_response += chunk
                    stream_response = ChatCompletionStreamResponse(
                        id=request_id,
                        created=created_time,
                        model=request.model,
                        choices=[ChatCompletionStreamChoice(
                            index=0,
                            delta={"content": chunk},
                            finish_reason=None
                        )]
                    )
                    yield f"data: {stream_response.model_dump_json()}\n\n"

            final_response = ChatCompletionStreamResponse(
                id=request_id,
                created=created_time,
                model=request.model,
                choices=[ChatCompletionStreamChoice(
                    index=0,
                    delta={},
                    finish_reason="stop"
                )]
            )
            yield f"data: {final_response.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"

            request_logger.log_stream_request_response(
                request.model_dump(), full_response, time.time() - start_time
            )
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    async def update_assistant_message():
        nonlocal full_response
        async for _ in llm_client.get_response_stream(messages, request.model):
            pass
        if assistant_msg_id:
            conversation_manager.update_message_content_and_time(
                assistant_msg_id,
                full_response,
                created_at=now
            )

    if assistant_msg_id:
        import asyncio
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