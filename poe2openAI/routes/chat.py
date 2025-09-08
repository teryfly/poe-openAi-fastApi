import json
import time
import uuid
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import Config
from models import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,
    ChatCompletionStreamResponse, ChatCompletionStreamChoice,
    ChatCompletionUsage, ChatMessage, Role
)
from logger import request_logger
from utils.attachments import save_upload, public_url, attachments_meta

router = APIRouter()
logger = logging.getLogger(__name__)
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials.credentials.startswith("sk-"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    return credentials.credentials

class SafeStreamWrapper:
    def __init__(self, poe_stream, active_generators):
        self.poe_stream = poe_stream
        self.closed = False
        self.active_generators = active_generators
        self.active_generators.add(self)
    async def close(self):
        if not self.closed:
            self.closed = True
            try:
                if hasattr(self.poe_stream, 'aclose'):
                    await self.poe_stream.aclose()
            finally:
                try:
                    self.active_generators.discard(self)
                except Exception:
                    pass
    async def iterate(self):
        try:
            async for chunk in self.poe_stream:
                if self.closed:
                    break
                yield chunk
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            raise
        finally:
            await self.close()

async def _stream_response(parsed: ChatCompletionRequest, request_obj: Request):
    poe_client = request_obj.app.state.poe_client
    if not poe_client:
        raise HTTPException(status_code=500, detail="Poe client not initialized")

    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_time = int(time.time())

    # Convert messages
    messages: List[Dict[str, Any]] = []
    for msg in parsed.messages:
        msg_dict: Dict[str, Any] = {"role": msg.role.value}
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

    async def gen():
        full = ""
        wrapper = SafeStreamWrapper(
            poe_client.get_response_stream(messages, parsed.model),
            request_obj.app.state.active_generators
        )
        try:
            async for chunk in wrapper.iterate():
                if chunk:
                    full += chunk
                    sse = ChatCompletionStreamResponse(
                        id=request_id,
                        created=created_time,
                        model=parsed.model,
                        choices=[
                            ChatCompletionStreamChoice(index=0, delta={"content": chunk})
                        ],
                    )
                    yield f"data: {sse.model_dump_json()}\n\n"
            done = ChatCompletionStreamResponse(
                id=request_id, created=created_time, model=parsed.model,
                choices=[ChatCompletionStreamChoice(index=0, delta={}, finish_reason="stop")]
            )
            yield f"data: {done.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
            request_logger.log_stream_request_response(parsed.model_dump(), full, 0.0)
        except Exception as e:
            err = {"error": {"message": str(e), "type": "internal_error"}}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
        finally:
            await wrapper.close()

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no"
    })

@router.post("/v1/chat/completions")
async def chat_completions(request: Request, api_key: str = Depends(verify_api_key)):
    poe_client = request.app.state.poe_client
    if not poe_client:
        raise HTTPException(status_code=500, detail="Poe client not initialized")

    content_type = request.headers.get("content-type", "")
    # multipart handling
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        model = (form.get("model") or "").strip()
        messages_raw = form.get("messages")
        text = form.get("text")
        stream_flag = str(form.get("stream") or "false").lower() == "true"

        if not model:
            raise HTTPException(status_code=400, detail="Missing 'model' field")

        uploads: List[UploadFile] = []
        for _, val in form.multi_items():
            if isinstance(val, UploadFile):
                uploads.append(val)

        saved: List[Dict[str, Any]] = []
        for uf in uploads:
            filename, ctype, size = save_upload(uf)
            url = public_url(filename, str(request.base_url).rstrip("/"))
            saved.append({"filename": filename, "content_type": ctype, "size": size, "url": url})

        if messages_raw:
            try:
                messages = json.loads(messages_raw)
                if not isinstance(messages, list):
                    raise ValueError("messages must be an array")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON in 'messages': {e}")
        else:
            if not text and not saved:
                raise HTTPException(status_code=400, detail="Either 'messages' or 'text' or files must be provided")
            messages = [{"role": "user", "content": (text or "").strip()}]

        # merge attachments into last user
        last_user = None
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], dict) and messages[i].get("role") == "user":
                last_user = i
                break

        lines = []
        for f in saved:
            lines.append(f"[ATTACHMENT] name={f['filename']} type={f['content_type']} size={f['size']} url={f['url']}")
            if f["content_type"].startswith("image/"):
                lines.append(f"[IMAGE_URL] {f['url']}")
        block = "\n".join(lines).strip()

        if block:
            if last_user is not None:
                existing = messages[last_user].get("content")
                if isinstance(existing, list):
                    for f in saved:
                        if f["content_type"].startswith("image/"):
                            messages[last_user]["content"].append({"type": "image_url", "image_url": {"url": f["url"]}})
                        messages[last_user]["content"].append({"type": "text", "text": f"[ATTACHMENT] name={f['filename']} type={f['content_type']} size={f['size']} url={f['url']}"})
                else:
                    base_text = (existing or "")
                    if base_text and not base_text.endswith("\n"):
                        base_text += "\n"
                    messages[last_user]["content"] = f"{base_text}{block}"
            else:
                messages.append({"role": "user", "content": block})

        pre_log = {"model": model, "messages": messages, "stream": stream_flag, "multipart": True, "meta": attachments_meta(saved)}

        try:
            parsed = ChatCompletionRequest(model=model, messages=[ChatMessage(**m) for m in messages], stream=stream_flag)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid messages structure: {e}")

        if parsed.stream:
            resp = await _stream_response(parsed, request)
            request_logger.log_request_response(pre_log, {"stream": True}, 0.0)
            return resp
        else:
            start = time.time()
            # convert messages to raw dict for poe client
            messages_oai: List[Dict[str, Any]] = []
            for msg in parsed.messages:
                d: Dict[str, Any] = {"role": msg.role.value}
                if msg.content is not None:
                    d["content"] = msg.content
                if msg.function_call:
                    d["function_call"] = msg.function_call.model_dump()
                if msg.tool_calls:
                    d["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
                if msg.name:
                    d["name"] = msg.name
                if msg.tool_call_id:
                    d["tool_call_id"] = msg.tool_call_id
                messages_oai.append(d)
            try:
                text_resp = await poe_client.get_response_complete(messages_oai, parsed.model)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
            resp = ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex}",
                created=int(time.time()),
                model=parsed.model,
                choices=[ChatCompletionChoice(index=0, message=ChatMessage(role=Role.ASSISTANT, content=text_resp), finish_reason="stop")],
                usage=ChatCompletionUsage(
                    prompt_tokens=sum(len(str(m.get('content', '')).split()) for m in messages_oai),
                    completion_tokens=len(text_resp.split()),
                    total_tokens=sum(len(str(m.get('content', '')).split()) for m in messages_oai) + len(text_resp.split())
                )
            )
            request_logger.log_request_response(pre_log, resp.model_dump(), time.time() - start)
            return resp

    # JSON branch (FastAPI body already handled by middleware in app factory)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        parsed = ChatCompletionRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {e}")

    if parsed.stream:
        return await _stream_response(parsed, request)

    # Non-streaming
    messages_oai: List[Dict[str, Any]] = []
    for msg in parsed.messages:
        d: Dict[str, Any] = {"role": msg.role.value}
        if msg.content is not None:
            d["content"] = msg.content
        if msg.function_call:
            d["function_call"] = msg.function_call.model_dump()
        if msg.tool_calls:
            d["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
        if msg.name:
            d["name"] = msg.name
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        messages_oai.append(d)
    text_resp = await request.app.state.poe_client.get_response_complete(messages_oai, parsed.model)
    resp = ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=parsed.model,
        choices=[ChatCompletionChoice(index=0, message=ChatMessage(role=Role.ASSISTANT, content=text_resp), finish_reason="stop")],
        usage=ChatCompletionUsage(
            prompt_tokens=sum(len(str(m.get('content', '')).split()) for m in messages_oai),
            completion_tokens=len(text_resp.split()),
            total_tokens=sum(len(str(m.get('content', '')).split()) for m in messages_oai) + len(text_resp.split())
        )
    )
    request_logger.log_request_response(parsed.model_dump(), resp.model_dump(), 0.0)
    return resp