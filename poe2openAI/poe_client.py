import fastapi_poe as fp
from typing import AsyncGenerator, List, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

class PoeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    @staticmethod
    def convert_role_to_poe(role: str) -> str:
        role_mapping = {
            'system': 'system',
            'user': 'user',
            'assistant': 'bot',
            'tool': 'user',
            'function': 'user'
        }
        return role_mapping.get((role or "user").lower(), 'user')
    
    async def get_response_stream(self, messages: List[Dict[str, Any]], model: str) -> AsyncGenerator[str, None]:
        try:
            poe_messages: List[fp.ProtocolMessage] = []
            for i, msg in enumerate(messages):
                poe_role = self.convert_role_to_poe(msg.get("role", "user"))
                content = msg.get("content", "")
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict):
                            t = item.get("type")
                            if t == "text":
                                parts.append(str(item.get("text", "")))
                            elif t == "image_url":
                                url = ""
                                data = item.get("image_url", {})
                                if isinstance(data, dict):
                                    url = data.get("url", "")
                                if url:
                                    parts.append(f"[IMAGE_URL] {url}")
                            else:
                                parts.append(f"[CONTENT_ITEM]{json.dumps(item, ensure_ascii=False)}[/CONTENT_ITEM]")
                        else:
                            parts.append(str(item))
                    content = "\n".join(parts)
                content_str = str(content or "")
                if content_str.strip():
                    poe_messages.append(fp.ProtocolMessage(role=poe_role, content=content_str))
                    logger.info(f"Poe msg {i}: {msg.get('role')} -> {poe_role}, len={len(content_str)}")
            async for partial in fp.get_bot_response(messages=poe_messages, bot_name=model, api_key=self.api_key):
                if hasattr(partial, 'text') and partial.text:
                    yield partial.text
        except Exception as e:
            logger.error(f"Poe stream error: {e}", exc_info=True)
            yield f"Error: {str(e)}"
    
    async def get_response_complete(self, messages: List[Dict[str, Any]], model: str) -> str:
        out = ""
        async for chunk in self.get_response_stream(messages, model):
            out += chunk
        return out