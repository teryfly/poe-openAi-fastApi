import aiohttp
import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List

from poe_client import PoeClient
from services.llm_errors import (
    LLMServiceError,
    LLMUpstreamNetworkError,
    LLMUpstreamResponseError,
    LLMUpstreamTimeoutError,
)
from services.poe_diagnostics import build_disconnect_debug_info, print_disconnect_debug_info
from services.poe_request_strategy import should_force_stream_aggregation_for_non_stream
from services.poe_stream_aggregate import get_response_complete_via_stream

logger = logging.getLogger(__name__)


def _extract_text_content(response_data: Dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message", {})
    if not isinstance(message, dict):
        return ""

    content = message.get("content", "")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif item is not None:
                parts.append(str(item))
        return "\n".join([p for p in parts if p]).strip()

    return str(content) if content is not None else ""


def _build_payload(model: str, prepared_messages: List[dict], kwargs: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"model": model, "messages": prepared_messages, "stream": False}
    if "temperature" in kwargs:
        payload["temperature"] = kwargs["temperature"]
    if "max_tokens" in kwargs:
        payload["max_tokens"] = kwargs["max_tokens"]
    if "top_p" in kwargs:
        payload["top_p"] = kwargs["top_p"]
    if "extra_body" in kwargs:
        payload.update(kwargs["extra_body"])
    return payload


def _is_server_disconnected_error(error: Exception) -> bool:
    return "server disconnected" in str(error).lower()


class ConfigurableTimeoutPoeClient(PoeClient):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.poe.com",
        non_stream_timeout_seconds: int = 300,
    ):
        super().__init__(api_key=api_key, base_url=base_url)
        self.non_stream_timeout_seconds = max(1, int(non_stream_timeout_seconds or 300))

    async def _request_non_stream_once(self, url: str, payload: Dict[str, Any], model: str, request_tag: str) -> str:
        timeout = aiohttp.ClientTimeout(total=self.non_stream_timeout_seconds)
        start_ts = time.time()

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=self.headers, json=payload) as resp:
                    elapsed = time.time() - start_ts
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error("[%s] non-stream status=%s model=%s elapsed=%.2fs", request_tag, resp.status, model, elapsed)
                        raise LLMUpstreamResponseError(
                            f"Poe API error: {resp.status} - {error_text}",
                            upstream_status=resp.status,
                        )

                    try:
                        response_data = await resp.json()
                    except Exception as e:
                        raw = await resp.text()
                        logger.error("[%s] invalid-json model=%s raw-len=%d", request_tag, model, len(raw))
                        raise LLMUpstreamResponseError(
                            f"Invalid JSON response from Poe API: {e}",
                            upstream_status=resp.status,
                        ) from e

                    content = _extract_text_content(response_data)
                    logger.info("[%s] non-stream success model=%s elapsed=%.2fs len=%d", request_tag, model, elapsed, len(content))
                    return content

        except asyncio.TimeoutError as e:
            raise LLMUpstreamTimeoutError(f"Request timeout after {self.non_stream_timeout_seconds}s") from e
        except aiohttp.ClientError as e:
            raise LLMUpstreamNetworkError(f"Network error calling Poe API: {str(e)}") from e

    async def get_response_complete(self, messages: List[dict], model: str, **kwargs) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        prepared_messages = self._prepare_messages(messages)
        payload = _build_payload(model, prepared_messages, kwargs)
        request_tag = f"{model}:{uuid.uuid4().hex[:8]}"
        request_start_ts = time.time()

        force_stream, reason, metrics = should_force_stream_aggregation_for_non_stream(
            model=model,
            prepared_messages=prepared_messages,
            payload=payload,
        )
        logger.info("[%s] non-stream strategy reason=%s metrics=%s", request_tag, reason, metrics)

        if force_stream:
            logger.warning("[%s] proactive stream-aggregation enabled reason=%s", request_tag, reason)
            return await get_response_complete_via_stream(
                base_url=self.base_url,
                headers=self.headers,
                model=model,
                prepared_messages=prepared_messages,
                timeout_seconds=self.non_stream_timeout_seconds,
                request_tag=request_tag,
                **kwargs,
            )

        try:
            return await self._request_non_stream_once(url, payload, model, request_tag)
        except LLMUpstreamNetworkError as e:
            if _is_server_disconnected_error(e):
                debug_info = build_disconnect_debug_info(
                    request_tag=request_tag,
                    model=model,
                    timeout_seconds=self.non_stream_timeout_seconds,
                    prepared_messages=prepared_messages,
                    payload=payload,
                    error=e,
                    elapsed_seconds=time.time() - request_start_ts,
                )
                logger.warning("[%s] non-stream disconnected debug=%s", request_tag, debug_info)
                print_disconnect_debug_info(debug_info)

                logger.warning("[%s] switching to stream aggregation fallback", request_tag)
                return await get_response_complete_via_stream(
                    base_url=self.base_url,
                    headers=self.headers,
                    model=model,
                    prepared_messages=prepared_messages,
                    timeout_seconds=self.non_stream_timeout_seconds,
                    request_tag=request_tag,
                    **kwargs,
                )
            logger.error("[%s] non-stream network error model=%s err=%s", request_tag, model, e)
            raise
        except (LLMUpstreamTimeoutError, LLMUpstreamResponseError):
            raise
        except LLMServiceError:
            raise
        except Exception as e:
            logger.error("[%s] unexpected non-stream error model=%s err=%s", request_tag, model, e)
            raise LLMUpstreamResponseError(f"Unexpected upstream error: {str(e)}") from e