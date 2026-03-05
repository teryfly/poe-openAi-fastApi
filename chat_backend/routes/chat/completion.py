import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from auth import verify_api_key
from conversation_manager import conversation_manager
from llm_router import get_llm_client
from logger import request_logger
from models import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamChoice,
    ChatCompletionStreamResponse,
    ChatCompletionUsage,
    ChatMessage,
    Role,
)
from services.message_utils import is_ignored_user_message
from services.poe_messages import normalize_messages_for_poe

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/v1/chat/completions")
async def create_chat_completion(request: Request, api_key: str = Depends(verify_api_key)):
    llm_client, _ = get_llm_client()
    start_time = time.time()
    body = await _parse_request_body(request)
    req_obj = ChatCompletionRequest(**body)

    raw_messages = _to_raw_messages(req_obj.messages)
    llm_messages = normalize_messages_for_poe(raw_messages)
    cid = _extract_cid(req_obj.messages)

    user_message_id = _persist_last_user_message_if_needed(cid, raw_messages)
    if req_obj.stream:
        return await _stream_response(llm_client, req_obj, llm_messages, start_time, cid, user_message_id)

    try:
        llm_kwargs = _build_llm_kwargs(req_obj)
        content = await llm_client.get_response_complete(llm_messages, req_obj.model, **llm_kwargs)
        _persist_assistant_if_needed(cid, content)
        response = _build_non_stream_response(req_obj.model, llm_messages, content)
        request_logger.log_request_response(req_obj.model_dump(), response.model_dump(), time.time() - start_time)
        return response
    except Exception as e:
        logger.error("Chat completion failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


async def _parse_request_body(request: Request) -> Dict[str, Any]:
    ct = (request.headers.get("content-type") or "").lower()
    if ct.startswith("application/json"):
        return await request.json()
    if "multipart/form-data" in ct:
        form = await request.form()
        model = str(form.get("model") or "").strip()
        if not model:
            raise HTTPException(status_code=400, detail="Missing 'model' field")
        stream = str(form.get("stream") or "false").lower() == "true"
        raw_messages = form.get("messages")
        text = str(form.get("text") or "").strip()
        messages: List[Dict[str, Any]] = []
        if raw_messages:
            try:
                messages = json.loads(raw_messages)
                if not isinstance(messages, list):
                    raise ValueError("messages must be a list")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON in 'messages': {e}")
        elif text:
            messages = [{"role": "user", "content": text}]
        else:
            raise HTTPException(status_code=400, detail="Either 'messages' or 'text' must be provided")
        return {"model": model, "stream": stream, "messages": messages}
    raise HTTPException(status_code=415, detail="Unsupported Content-Type")


def _to_raw_messages(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
    return [{"role": m.role.value, "content": m.content or ""} for m in messages]


def _extract_cid(messages: List[ChatMessage]) -> Optional[str]:
    for msg in messages:
        name = (msg.name or "").strip()
        if name.startswith("cid-"):
            return name[4:]
    return None


def _persist_last_user_message_if_needed(cid: Optional[str], messages: List[Dict[str, Any]]) -> Optional[int]:
    if not cid:
        return None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if is_ignored_user_message("user", content):
                return None
            try:
                return conversation_manager.append_message(cid, "user", content, created_at=datetime.now())
            except Exception:
                return None
    return None


def _persist_assistant_if_needed(cid: Optional[str], content: str) -> None:
    if cid:
        try:
            conversation_manager.append_message(cid, "assistant", content, created_at=datetime.now())
        except Exception:
            pass


def _build_llm_kwargs(req_obj: ChatCompletionRequest) -> Dict[str, Any]:
    return {
        "temperature": req_obj.temperature,
        "max_tokens": req_obj.max_tokens,
        "top_p": req_obj.top_p,
        "extra_body": req_obj.extra_body,
    }


def _build_non_stream_response(model: str, llm_messages: List[Dict[str, Any]], content: str) -> ChatCompletionResponse:
    p = sum(len(str(x.get("content", "")).split()) for x in llm_messages)
    c = len(content.split())
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=model,
        choices=[ChatCompletionChoice(index=0, message=ChatMessage(role=Role.ASSISTANT, content=content), finish_reason="stop")],
        usage=ChatCompletionUsage(prompt_tokens=p, completion_tokens=c, total_tokens=p + c),
    )


async def _stream_response(llm_client, req_obj: ChatCompletionRequest, llm_messages: List[Dict[str, Any]], start_time: float, cid: Optional[str], user_message_id: Optional[int]):
    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_time = int(time.time())
    full_response = ""
    assistant_id = None
    if cid:
        try:
            assistant_id = conversation_manager.insert_assistant_placeholder(cid, created_at=datetime.now())
        except Exception:
            assistant_id = None

    async def generate():
        nonlocal full_response
        try:
            kwargs = _build_llm_kwargs(req_obj)
            async for chunk in llm_client.get_response_stream(llm_messages, req_obj.model, **kwargs):
                if not chunk:
                    continue
                full_response += chunk
                data = ChatCompletionStreamResponse(
                    id=request_id,
                    created=created_time,
                    model=req_obj.model,
                    choices=[ChatCompletionStreamChoice(index=0, delta={"content": chunk}, finish_reason=None)],
                )
                yield f"data: {data.model_dump_json()}\n\n"
            if assistant_id:
                conversation_manager.update_message_content_and_time(assistant_id, full_response, created_at=datetime.now())
            yield f"data: {ChatCompletionStreamResponse(id=request_id, created=created_time, model=req_obj.model, choices=[ChatCompletionStreamChoice(index=0, delta={}, finish_reason='stop')]).model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
            request_logger.log_stream_request_response(req_obj.model_dump(), full_response, time.time() - start_time)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'user_message_id': user_message_id})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})