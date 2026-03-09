import aiohttp
import asyncio
import json
import logging
import time
from typing import Any, Dict

from services.llm_errors import (
    LLMUpstreamNetworkError,
    LLMUpstreamResponseError,
    LLMUpstreamTimeoutError,
)

logger = logging.getLogger(__name__)


def _build_stream_payload(model: str, messages: list, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
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
    return payload


async def get_response_complete_via_stream(
    base_url: str,
    headers: Dict[str, str],
    model: str,
    prepared_messages: list,
    timeout_seconds: int,
    request_tag: str,
    **kwargs,
) -> str:
    """
    Aggregate streaming response as a non-stream fallback.
    This mitigates long non-stream waits that may be disconnected by upstream proxies.
    """
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = _build_stream_payload(model, prepared_messages, kwargs)
    timeout = aiohttp.ClientTimeout(total=max(1, int(timeout_seconds)))

    start_ts = time.time()
    first_chunk_latency = None
    chunk_count = 0
    full_content = ""

    logger.warning(
        "[%s] Falling back to stream aggregation for model=%s due to non-stream disconnect risk",
        request_tag,
        model,
    )

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("[%s] Stream fallback upstream status=%s body=%s", request_tag, resp.status, body)
                    raise LLMUpstreamResponseError(
                        f"Poe API stream fallback error: {resp.status} - {body}",
                        upstream_status=resp.status,
                    )

                async for raw_chunk in resp.content:
                    if not raw_chunk:
                        continue

                    text = raw_chunk.decode("utf-8", errors="ignore")
                    for line in text.splitlines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue

                        data_part = line[6:]
                        if data_part == "[DONE]":
                            elapsed = time.time() - start_ts
                            logger.info(
                                "[%s] Stream fallback completed model=%s elapsed=%.2fs chunks=%d len=%d",
                                request_tag,
                                model,
                                elapsed,
                                chunk_count,
                                len(full_content),
                            )
                            return full_content

                        try:
                            chunk_data = json.loads(data_part)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk_data.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {}) if isinstance(choices[0], dict) else {}
                        content = delta.get("content", "")
                        if not content or str(content).strip().startswith("Thinking..."):
                            continue

                        if first_chunk_latency is None:
                            first_chunk_latency = time.time() - start_ts
                            logger.info(
                                "[%s] Stream fallback first chunk model=%s latency=%.2fs",
                                request_tag,
                                model,
                                first_chunk_latency,
                            )

                        chunk_count += 1
                        full_content += str(content)

                elapsed = time.time() - start_ts
                logger.info(
                    "[%s] Stream fallback ended without DONE model=%s elapsed=%.2fs chunks=%d len=%d",
                    request_tag,
                    model,
                    elapsed,
                    chunk_count,
                    len(full_content),
                )
                return full_content

    except asyncio.TimeoutError as e:
        elapsed = time.time() - start_ts
        msg = f"Stream fallback timeout after {timeout_seconds}s"
        logger.error("[%s] %s model=%s elapsed=%.2fs", request_tag, msg, model, elapsed)
        raise LLMUpstreamTimeoutError(msg) from e
    except aiohttp.ClientError as e:
        elapsed = time.time() - start_ts
        msg = f"Stream fallback network error: {e}"
        logger.error("[%s] %s model=%s elapsed=%.2fs", request_tag, msg, model, elapsed)
        raise LLMUpstreamNetworkError(msg) from e
    except Exception as e:
        elapsed = time.time() - start_ts
        msg = f"Stream fallback unexpected error: {e}"
        logger.error("[%s] %s model=%s elapsed=%.2fs", request_tag, msg, model, elapsed)
        raise LLMUpstreamResponseError(msg) from e