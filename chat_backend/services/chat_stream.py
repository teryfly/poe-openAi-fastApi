import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, List, Any
from conversation_manager import conversation_manager
class StreamSession:
    """
    基于线程的流式会话，负责从 LLM 客户端获取分片并累积，同时在完成后落库。
    """
    def __init__(self, session_id: str, llm_client, chat_messages: List[Dict[str, Any]], model: str, assistant_msg_id: int, now: datetime):
        self.session_id = session_id
        self.llm_client = llm_client
        self.chat_messages = chat_messages
        self.model = model
        self.assistant_msg_id = assistant_msg_id
        self.now = now
        self.full_response = ""
        self.stopped = threading.Event()
        self.completed = threading.Event()
        self.exception: Optional[Exception] = None
        self.thread: Optional[threading.Thread] = None
        self.chunks: List[str] = []
        self.lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    def stop(self):
        self.stopped.set()
    def is_completed(self) -> bool:
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
                if not chunk:
                    continue
                # 过滤以 "Thinking..." 开头的内容
                if chunk.strip().startswith("Thinking..."):
                    continue
                with self.lock:
                    self.chunks.append(chunk)
                self.full_response += chunk
        except Exception as e:
            self.exception = e
        finally:
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
    def get_chunks(self, start_idx: int) -> List[str]:
        with self.lock:
            return self.chunks[start_idx:]
_stream_sessions: Dict[str, StreamSession] = {}
_sessions_lock = threading.Lock()
def get_session(session_id: str) -> Optional[StreamSession]:
    with _sessions_lock:
        return _stream_sessions.get(session_id)
def add_session(session_id: str, session: StreamSession):
    with _sessions_lock:
        _stream_sessions[session_id] = session
def remove_session(session_id: str):
    with _sessions_lock:
        _stream_sessions.pop(session_id, None)