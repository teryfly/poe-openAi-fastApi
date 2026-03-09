import json
import os
from typing import Any, Dict, List, Tuple


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, min_value: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(str(raw).strip())
        return max(min_value, value)
    except Exception:
        return default


def _env_model_set(name: str) -> set:
    raw = os.getenv(name, "")
    if not raw.strip():
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def summarize_prepared_messages(prepared_messages: List[dict]) -> Dict[str, Any]:
    role_counts: Dict[str, int] = {}
    total_text_chars = 0
    multimodal_messages = 0

    for msg in prepared_messages:
        role = str(msg.get("role", "unknown"))
        role_counts[role] = role_counts.get(role, 0) + 1

        content = msg.get("content", "")
        if isinstance(content, str):
            total_text_chars += len(content)
        elif isinstance(content, list):
            multimodal_messages += 1
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    total_text_chars += len(str(item.get("text", "")))

    return {
        "message_count": len(prepared_messages),
        "role_counts": role_counts,
        "total_text_chars": total_text_chars,
        "multimodal_messages": multimodal_messages,
    }


def should_force_stream_aggregation_for_non_stream(
    model: str,
    prepared_messages: List[dict],
    payload: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Decide whether non-stream request should proactively use stream aggregation.

    Env configs:
    - POE_NON_STREAM_FORCE_STREAM_ENABLED=true|false (default true)
    - POE_NON_STREAM_FORCE_STREAM_PROMPT_CHARS (default 30000)
    - POE_NON_STREAM_FORCE_STREAM_PAYLOAD_CHARS (default 45000)
    - POE_NON_STREAM_FORCE_STREAM_MODELS=Claude-Sonnet-4.5,GPT-5.2
    """
    enabled = _env_bool("POE_NON_STREAM_FORCE_STREAM_ENABLED", True)
    prompt_chars_threshold = _env_int("POE_NON_STREAM_FORCE_STREAM_PROMPT_CHARS", 30000, 0)
    payload_chars_threshold = _env_int("POE_NON_STREAM_FORCE_STREAM_PAYLOAD_CHARS", 45000, 0)
    force_models = _env_model_set("POE_NON_STREAM_FORCE_STREAM_MODELS")

    payload_size_chars = len(json.dumps(payload, ensure_ascii=False))
    msg_summary = summarize_prepared_messages(prepared_messages)

    metrics = {
        "enabled": enabled,
        "model": model,
        "payload_size_chars": payload_size_chars,
        "prompt_chars_threshold": prompt_chars_threshold,
        "payload_chars_threshold": payload_chars_threshold,
        "force_models": sorted(list(force_models)),
        "messages_summary": msg_summary,
    }

    if not enabled:
        return False, "disabled", metrics

    if model in force_models:
        return True, "model_in_force_list", metrics

    if payload_size_chars >= payload_chars_threshold:
        return True, "payload_size_threshold", metrics

    if msg_summary["total_text_chars"] >= prompt_chars_threshold:
        return True, "prompt_chars_threshold", metrics

    return False, "below_threshold", metrics