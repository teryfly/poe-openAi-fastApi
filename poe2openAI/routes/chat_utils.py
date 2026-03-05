import uuid
import time
from typing import Any, Dict, List

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from models import (
    ChatMessage,
    Role,
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatCompletionUsage,
)

security = HTTPBearer()


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials.credentials.startswith("sk-"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    return credentials.credentials


def replace_poe_domain(text: str) -> str:
    if not text:
        return text
    return text.replace("poe.com/api_key", "fastable.cn")


def messages_to_dict(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for msg in messages:
        item: Dict[str, Any] = {"role": msg.role.value}
        if msg.content is not None:
            item["content"] = msg.content
        if msg.function_call:
            item["function_call"] = msg.function_call.model_dump()
        if msg.tool_calls:
            item["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
        if msg.name:
            item["name"] = msg.name
        if msg.tool_call_id:
            item["tool_call_id"] = msg.tool_call_id
        out.append(item)
    return out


def _estimate_tokens_from_content(content: Any) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content.split())
    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                total += len(str(item.get("text", "")).split())
            else:
                total += len(str(item).split())
        return total
    return len(str(content).split())


def estimate_prompt_tokens(messages: List[Dict[str, Any]]) -> int:
    return sum(_estimate_tokens_from_content(m.get("content")) for m in messages)


def build_completion_response(model: str, response_text: str, request_messages: List[Dict[str, Any]]) -> ChatCompletionResponse:
    prompt_tokens = estimate_prompt_tokens(request_messages)
    completion_tokens = len((response_text or "").split())
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role=Role.ASSISTANT, content=response_text),
                finish_reason="stop",
            )
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


def sanitize_messages_for_log(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []

    for msg in messages:
        item = dict(msg)
        content = item.get("content")

        if isinstance(content, list):
            cleaned_content = []
            for c in content:
                if not isinstance(c, dict):
                    cleaned_content.append(c)
                    continue

                c_item = dict(c)
                if c_item.get("type") == "image_url":
                    data = c_item.get("image_url", {})
                    if isinstance(data, dict) and str(data.get("url", "")).startswith("data:"):
                        c_item["image_url"] = {"url": "[DATA_URL_OMITTED]"}
                elif c_item.get("type") == "file":
                    data = c_item.get("file", {})
                    if isinstance(data, dict) and str(data.get("file_data", "")).startswith("data:"):
                        c_item["file"] = {
                            "filename": data.get("filename", "file"),
                            "file_data": "[DATA_URL_OMITTED]",
                        }

                cleaned_content.append(c_item)

            item["content"] = cleaned_content

        sanitized.append(item)

    return sanitized