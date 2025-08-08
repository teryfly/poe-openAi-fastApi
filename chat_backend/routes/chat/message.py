import json
import asyncio
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Path, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict

from conversation_manager import conversation_manager
from llm_router import get_llm_client
from auth import verify_api_key
from config import Config

router = APIRouter()

class AddMessageRequest(BaseModel):
    role: str
    content: str
    model: str = "ChatGPT-4o-Latest"
    stream: bool = False

def is_ignored_user_message(role: str, content: str) -> bool:
    if role.lower() == "user":
        trimmed = content.strip()
        return trimmed in [msg.strip() for msg in Config.ignoredUserMessages]
    return False

def merge_assistant_messages_with_user_history(messages, user_role=None, user_content=None, ignore_user=False):
    result = []
    temp_assistant = []
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
            if temp_assistant:
                merged = "\n---\n".join(temp_assistant)
                result.append({"role": "assistant", "content": merged})
                temp_assistant = []
            result.append({"role": role, "content": content})
    if temp_assistant:
        merged = "\n---\n".join(temp_assistant)
        result.append({"role": "assistant", "content": merged})
    return result

# ====== 全局流式会话状态管理 ======
class StreamSession:
    def __init__(self, session_id, llm_client, chat_messages, model, assistant_msg_id, now):
        self.session_id = session_id
        self.llm_client = llm_client
        self.chat_messages = chat_messages
        self.model = model
        self.assistant_msg_id = assistant_msg_id
        self.now = now
        self.full_response = ""
        self.stopped = threading.Event()
        self.completed = threading.Event()
        self.last_chunk = None
        self.exception = None
        self.thread = None
        self.chunks = []
        self.lock = threading.Lock()
        self._loop = None

    def stop(self):
        self.stopped.set()

    def is_completed(self):
        return self.completed.is_set()

    def start(self):
        self.thread = threading.Thread(target=self._run_stream, daemon=True)
        self.thread.start()

    def _run_stream(self):
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            self._loop = asyncio.get_event_loop()
            self._loop.run_until_complete(self._stream())
        except Exception as e:
            self.exception = e
        finally:
            self.completed.set()

    async def _stream(self):
        try:
            async for chunk in self.llm_client.get_response_stream(self.chat_messages, self.model):
                if self.stopped.is_set():
                    break
                if chunk:
                    # 严格过滤：凡是以 "Thinking..." 开头的消息直接忽略
                    if chunk.strip().startswith("Thinking..."):
                        continue
                    
                    with self.lock:
                        self.chunks.append(chunk)
                    self.full_response += chunk
        except Exception as e:
            self.exception = e
        finally:
            # 落库
            if self.assistant_msg_id:
                try:
                    conversation_manager.update_message_content_and_time(
                        self.assistant_msg_id,
                        self.full_response,
                        created_at=self.now
                    )
                except Exception:
                    pass
            self.completed.set()

    def get_chunks(self, start_idx):
        with self.lock:
            return self.chunks[start_idx:]

_stream_sessions: Dict[str, StreamSession] = {}
_sessions_lock = threading.Lock()

def get_session(session_id) -> Optional[StreamSession]:
    with _sessions_lock:
        return _stream_sessions.get(session_id)

def add_session(session_id, session: StreamSession):
    with _sessions_lock:
        _stream_sessions[session_id] = session

def remove_session(session_id):
    with _sessions_lock:
        _stream_sessions.pop(session_id, None)

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
    api_key: str = Depends(verify_api_key),
    fastapi_request: Request = None,
):
    llm_client, backend = get_llm_client()
    try:
        if request.stream:
            return await create_conversation_stream_response(
                conversation_id,
                user_role=request.role,
                user_content=request.content,
                model=request.model,
                fastapi_request=fastapi_request
            )
        ignore_user = is_ignored_user_message(request.role, request.content)
        user_message_id = None
        if not ignore_user:
            user_message_id = conversation_manager.append_message(conversation_id, request.role, request.content)
        messages = conversation_manager.get_messages(conversation_id)
        chat_messages = merge_assistant_messages_with_user_history(
            messages,
            user_role=request.role,
            user_content=request.content,
            ignore_user=ignore_user
        )
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

async def create_conversation_stream_response(conversation_id, user_role, user_content, model, fastapi_request: Request = None):
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
    session_id = f"{conversation_id}:{assistant_msg_id}:{int(now.timestamp() * 1000)}"

    session = StreamSession(
        session_id=session_id,
        llm_client=llm_client,
        chat_messages=chat_messages,
        model=model,
        assistant_msg_id=assistant_msg_id,
        now=now
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
            pass

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