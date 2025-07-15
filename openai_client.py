import aiohttp
from typing import AsyncGenerator, List
import logging
from config import Config

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        self.base_url = (base_url or Config.OPENAI_BASE_URL).rstrip("/")

    async def get_response_stream(self, messages: List[dict], model: str) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"OpenAI API error: {resp.status} {text}")
                    yield f"Error: {text}"
                    return
                async for line in resp.content:
                    if not line:
                        continue
                    try:
                        l = line.decode().strip()
                        if l.startswith("data: "):
                            data = l[6:]
                            if data == "[DONE]":
                                break
                            import json
                            payload = json.loads(data)
                            if "choices" in payload:
                                delta = payload["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                    except Exception as e:
                        logger.error(f"Parse stream error: {e}")
                        yield f"[Stream Error: {e}]"

    async def get_response_complete(self, messages: List[dict], model: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"OpenAI API error: {resp.status} {text}")
                    raise Exception(f"OpenAI API error: {resp.status} {text}")
                data = await resp.json()
                return data["choices"][0]["message"]["content"]