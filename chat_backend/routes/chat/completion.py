import uuid
import time
import json
import logging
import re  # 新增导入正则模块
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, UploadFile, File, Form, Request
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
from services.attachments import save_upload, build_attachment_text_line, is_image

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/v1/chat/completions")
async def create_chat_completion(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    llm_client, backend = get_llm_client()
    start_time = time.time()

    # 根据 Content-Type 判断是 JSON 还是 multipart
    content_type = (request.headers.get("content-type") or "").lower()
    if content_type.startswith("application/json"):
        body = await request.json()
        try:
            parsed = ChatCompletionRequest(**body)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")
        messages = _normalize_messages_from_pydantic(parsed)
        return await _handle_chat_flow(llm_client, backend, parsed, messages, start_time)
    elif "multipart/form-data" in content_type:
        form = await request.form()
        model = (form.get("model") or "").strip()
        if not model:
            raise HTTPException(status_code=400, detail="Missing 'model' field")
        stream_flag = str(form.get("stream") or "false").lower() == "true"
        # messages 可选（JSON 字符串）
        messages_raw = form.get("messages")
        text = form.get("text")

        # 收集文件
        uploads: list[UploadFile] = []
        for key, val in form.multi_items():
            if isinstance(val, UploadFile):
                uploads.append(val)

        if not messages_raw and not text and not uploads:
            raise HTTPException(status_code=400, detail="Either 'messages' or 'text' or files must be provided")

        # 解析 messages 或构造基础消息
        messages_list: list[dict] = []
        if messages_raw:
            try:
                msgs_json = json.loads(messages_raw)
                # 允许简化数组，保证是 list
                if not isinstance(msgs_json, list):
                    raise ValueError("messages must be an array")
                # 扁平化 OpenAI 内容数组为文本
                for m in msgs_json:
                    role = m.get("role", "user")
                    content = m.get("content", "")
                    # 若 content 是数组，提取 text 字段拼接
                    if isinstance(content, list):
                        parts = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                parts.append(item["text"])
                        content = "\n".join(parts)
                    messages_list.append({"role": role, "content": str(content)})
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON in 'messages': {e}")
        elif text:
            messages_list = [{"role": "user", "content": str(text)}]

        # 处理附件：保存并把 URL 以文本注入到最后一条 user 消息
        attachment_meta = []
        for f in uploads:
            try:
                url, path, size = save_upload(f)
                line = build_attachment_text_line(url, f.filename or "file", f.content_type or "", size)
                attachment_meta.append({"name": f.filename, "type": f.content_type, "size": size, "url": url})
                # 注入到最后一个 user 消息；如果没有 user，则追加一条
                inserted = False
                for i in range(len(messages_list) - 1, -1, -1):
                    if messages_list[i].get("role") == "user":
                        # 若为图片，额外添加 [IMAGE_URL] 行，帮助视觉模型
                        prefix = ""
                        if is_image(f.content_type or ""):
                            prefix = f"[IMAGE_URL] {url}\n"
                        messages_list[i]["content"] = (messages_list[i].get("content") or "") + \
                                                      ("\n\n" if messages_list[i].get("content") else "") + \
                                                      prefix + line
                        inserted = True
                        break
                if not inserted:
                    prefix = f"[IMAGE_URL] {url}\n" if is_image(f.content_type or "") else ""
                    messages_list.append({"role": "user", "content": prefix + line})
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Save file failed: {e}")

        # 组装兼容的请求对象
        chat_req = ChatCompletionRequest(
            model=model,
            messages=[ChatMessage(role=Role(m["role"]), content=m["content"]) for m in messages_list],
            stream=stream_flag
        )
        # 记录日志（包含附件元数据）
        try:
            req_log = chat_req.model_dump()
            if attachment_meta:
                req_log["attachments"] = attachment_meta
        except Exception:
            req_log = {"model": model, "messages": messages_list, "stream": stream_flag, "attachments": attachment_meta}

        messages = []
        for m in messages_list:
            messages.append({"role": m["role"], "content": m["content"]})

        # 流式或非流式
        try:
            if stream_flag:
                return await _stream_response(llm_client, backend, chat_req, messages, start_time)
            else:
                response_content = await llm_client.get_response_complete(messages, model)
                response = ChatCompletionResponse(
                    id=f"chatcmpl-{uuid.uuid4().hex}",
                    created=int(time.time()),
                    model=model,
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
                    req_log,
                    response.model_dump(),
                    time.time() - start_time
                )
                return response
        except Exception as e:
            logger.error(f"Error in chat completion (multipart): {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=415, detail="Unsupported Content-Type")

def _normalize_messages_from_pydantic(parsed: ChatCompletionRequest) -> list[dict]:
    messages = []
    for msg in parsed.messages:
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
    return messages

async def _handle_chat_flow(llm_client, backend, request_obj: ChatCompletionRequest, messages: list[dict], start_time: float):
    try:
        if request_obj.stream:
            conversation_id = None
            for msg in request_obj.messages:
                if hasattr(msg, "conversation_id"):
                    conversation_id = msg.conversation_id
                    break
                if hasattr(msg, "name") and str(msg.name).startswith("cid-"):
                    conversation_id = str(msg.name)[4:]
                    break

            return await _stream_response(
                llm_client, backend, request_obj, messages, start_time, conversation_id=conversation_id
            )
        else:
            response_content = await llm_client.get_response_complete(messages, request_obj.model)
            response = ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex}",
                created=int(time.time()),
                model=request_obj.model,
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
                request_obj.model_dump(),
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

    if conversation_id:
        try:
            assistant_msg_id = conversation_manager.insert_assistant_placeholder(conversation_id, created_at=now)
        except Exception as e:
            logger.warning(f"Insert assistant placeholder failed: {e}")

    async def generate():
        nonlocal full_response
        try:
            async for chunk in llm_client.get_response_stream(messages, request.model):
                if chunk:
                    # 严格过滤：凡是以 "Thinking..." 开头的消息直接忽略
                    if chunk.strip().startswith("Thinking..."):
                        continue
                    
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

            # 记录 multipart 或 json 的请求日志
            try:
                req_log = request.model_dump()
            except Exception:
                req_log = {"model": getattr(request, "model", None), "messages": messages, "stream": True}
            request_logger.log_stream_request_response(
                req_log, full_response, time.time() - start_time
            )
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    async def update_assistant_message():
        nonlocal full_response
        filtered_response = ""
        async for chunk in llm_client.get_response_stream(messages, request.model):
            if chunk and not chunk.strip().startswith("Thinking..."):
                filtered_response += chunk
        if assistant_msg_id:
            conversation_manager.update_message_content_and_time(
                assistant_msg_id,
                filtered_response,
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