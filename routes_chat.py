import time
import uuid
import asyncio
import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request, Path, Body
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from models import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,
    ChatMessage, Role, ChatCompletionUsage,
    ChatCompletionStreamResponse, ChatCompletionStreamChoice,
    BaseModel, ModelListResponse
)
from llm_router import get_llm_client, LLMBackend
from conversation_manager import conversation_manager
from logger import request_logger

logger = logging.getLogger(__name__)
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials.credentials.startswith("sk-test") and not credentials.credentials.startswith("poe-sk"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    return credentials.credentials

def register_chat_routes(app):
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
            if msg.content is not None:
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
                return await _stream_response(llm_client, backend, request, messages, start_time)
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

    async def _stream_response(llm_client, backend, request, messages, start_time):
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        created_time = int(time.time())
        full_response = ""
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
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )

    # ------------------ 多轮会话 API ------------------
    class ConversationCreateRequest(BaseModel):
        system_prompt: str = None

    class AddMessageRequest(BaseModel):
        role: str
        content: str
        model: str = "ChatGPT-4o-Latest"
        stream: bool = False

    @router.post("/v1/chat/conversations")
    async def create_conversation_api(request: ConversationCreateRequest = Body(...)):
        conversation_id = conversation_manager.create_conversation(request.system_prompt)
        return {"conversation_id": conversation_id}

    @router.get("/v1/chat/conversations/{conversation_id}/messages")
    async def get_conversation_history(conversation_id: str = Path(...)):
        try:
            messages = conversation_manager.get_messages(conversation_id)
            return {"conversation_id": conversation_id, "messages": messages}
        except KeyError:
            raise HTTPException(status_code=404, detail="Conversation not found")

    async def create_conversation_stream_response(conversation_id, user_role, user_content, model):
        llm_client, backend = get_llm_client()
        conversation_manager.append_message(conversation_id, user_role, user_content)
        messages = conversation_manager.get_messages(conversation_id)
        chat_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]
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
        async def append_assistant_once():
            nonlocal full_response
            async for _ in llm_client.get_response_stream(chat_messages, model):
                pass
            conversation_manager.append_message(conversation_id, "assistant", full_response)
        asyncio.create_task(append_assistant_once())
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )

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

    app.include_router(router)