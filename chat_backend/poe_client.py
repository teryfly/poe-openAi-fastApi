import aiohttp
import json
import logging
import time
from datetime import datetime
from typing import AsyncGenerator, List

logger = logging.getLogger(__name__)


class PoeClient:
    """
    Official Poe API Client
    Based on Poe's OpenAI-compatible API documentation
    """

    def __init__(self, api_key: str, base_url: str = "https://api.poe.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _now_str() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _prepare_messages(self, messages: List[dict]) -> List[dict]:
        """
        Prepare messages for Poe API.
        Handle content conversion and file attachments.
        """
        prepared = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, str):
                prepared.append({"role": role, "content": content})
                continue

            if isinstance(content, list):
                text_parts = []
                content_items = []

                for item in content:
                    if not isinstance(item, dict):
                        continue

                    item_type = item.get("type")
                    if item_type == "text":
                        text_parts.append(item.get("text", ""))
                    elif item_type == "image_url":
                        img_url = item.get("image_url", {})
                        if isinstance(img_url, dict):
                            url = img_url.get("url", "")
                        else:
                            url = str(img_url)
                        content_items.append(
                            {"type": "image_url", "image_url": {"url": url}}
                        )
                    elif item_type == "file":
                        file_info = item.get("file", {})
                        if isinstance(file_info, dict):
                            content_items.append(
                                {
                                    "type": "file",
                                    "file": {
                                        "filename": file_info.get("filename", "file"),
                                        "file_data": file_info.get("file_data", ""),
                                    },
                                }
                            )

                if content_items:
                    if text_parts:
                        content_items.insert(0, {"type": "text", "text": "\n".join(text_parts)})
                    prepared.append({"role": role, "content": content_items})
                else:
                    prepared.append({"role": role, "content": "\n".join(text_parts)})
                continue

            prepared.append({"role": role, "content": str(content)})

        return prepared

    async def get_response_stream(
        self, messages: List[dict], model: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Get streaming response from Poe API.
        """
        url = f"{self.base_url}/v1/chat/completions"
        prepared_messages = self._prepare_messages(messages)

        payload = {
            "model": model,
            "messages": prepared_messages,
            "stream": True,
        }
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "extra_body" in kwargs:
            payload.update(kwargs["extra_body"])

        start_ts = time.time()
        print(f"[{self._now_str()}] 🚀 请求 Poe.com LLM - 模型: {model} (流式)")

        first_chunk_latency = None
        chunk_count = 0

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        elapsed = time.time() - start_ts
                        print(
                            f"[{self._now_str()}] ❌ Poe API 错误 - 模型: {model}, "
                            f"耗时: {elapsed:.2f}s, 状态码: {resp.status}"
                        )
                        logger.error("Poe API error: %s - %s", resp.status, error_text)
                        yield f"Error: Poe API returned status {resp.status}"
                        return

                    async for line in resp.content:
                        if not line:
                            continue

                        decoded = line.decode("utf-8").strip()
                        if not decoded or not decoded.startswith("data: "):
                            continue

                        data_str = decoded[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            chunk_data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk_data.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if not content:
                            continue

                        if content.strip().startswith("Thinking..."):
                            continue

                        if first_chunk_latency is None:
                            first_chunk_latency = time.time() - start_ts
                            print(
                                f"[{self._now_str()}] 📥 首个响应片段 - 模型: {model}, "
                                f"延迟: {first_chunk_latency:.2f}s"
                            )

                        chunk_count += 1
                        yield content

            elapsed = time.time() - start_ts
            print(
                f"[{self._now_str()}] ✅ Poe API 流式响应完成 - 模型: {model}, "
                f"总耗时: {elapsed:.2f}s, 片段数: {chunk_count}"
            )

        except aiohttp.ClientError as e:
            elapsed = time.time() - start_ts
            print(
                f"[{self._now_str()}] ❌ 网络错误 - 模型: {model}, "
                f"耗时: {elapsed:.2f}s, 错误: {e}"
            )
            logger.error("Network error calling Poe API: %s", e)
            yield f"Error: Network error - {str(e)}"
        except Exception as e:
            elapsed = time.time() - start_ts
            print(
                f"[{self._now_str()}] ❌ 未知错误 - 模型: {model}, "
                f"耗时: {elapsed:.2f}s, 错误: {e}"
            )
            logger.error("Unexpected error calling Poe API: %s", e)
            yield f"Error: {str(e)}"

    async def get_response_complete(self, messages: List[dict], model: str, **kwargs) -> str:
        """
        Get complete (non-streaming) response from Poe API.
        """
        url = f"{self.base_url}/v1/chat/completions"
        prepared_messages = self._prepare_messages(messages)

        payload = {
            "model": model,
            "messages": prepared_messages,
            "stream": False,
        }
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "extra_body" in kwargs:
            payload.update(kwargs["extra_body"])

        start_ts = time.time()
        print(f"[{self._now_str()}] 🚀 请求 Poe.com LLM - 模型: {model} (非流式)")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as resp:
                    elapsed = time.time() - start_ts

                    if resp.status != 200:
                        error_text = await resp.text()
                        print(
                            f"[{self._now_str()}] ❌ Poe API 错误 - 模型: {model}, "
                            f"耗时: {elapsed:.2f}s, 状态码: {resp.status}"
                        )
                        logger.error("Poe API error: %s - %s", resp.status, error_text)
                        raise Exception(f"Poe API error: {resp.status} - {error_text}")

                    response_data = await resp.json()
                    choices = response_data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        print(
                            f"[{self._now_str()}] ✅ Poe API 响应完成 - 模型: {model}, "
                            f"耗时: {elapsed:.2f}s, 内容长度: {len(content)} 字符"
                        )
                        return content

                    print(
                        f"[{self._now_str()}] ⚠️ Poe API 响应为空 - 模型: {model}, "
                        f"耗时: {elapsed:.2f}s"
                    )
                    return ""

        except aiohttp.ClientError as e:
            elapsed = time.time() - start_ts
            print(
                f"[{self._now_str()}] ❌ 网络错误 - 模型: {model}, "
                f"耗时: {elapsed:.2f}s, 错误: {e}"
            )
            logger.error("Network error calling Poe API: %s", e)
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            elapsed = time.time() - start_ts
            print(
                f"[{self._now_str()}] ❌ 错误 - 模型: {model}, "
                f"耗时: {elapsed:.2f}s, 错误: {e}"
            )
            logger.error("Error calling Poe API: %s", e)
            raise