import json
import traceback
from datetime import datetime
from typing import Any, Dict, List


def _safe_len(value: Any) -> int:
    try:
        return len(value)  # type: ignore[arg-type]
    except Exception:
        return 0


def summarize_messages(prepared_messages: List[dict]) -> Dict[str, Any]:
    role_counts: Dict[str, int] = {}
    multimodal_messages = 0
    text_messages = 0
    total_text_chars = 0

    for msg in prepared_messages:
        role = str(msg.get("role", "unknown"))
        role_counts[role] = role_counts.get(role, 0) + 1

        content = msg.get("content", "")
        if isinstance(content, str):
            text_messages += 1
            total_text_chars += len(content)
        elif isinstance(content, list):
            multimodal_messages += 1
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    total_text_chars += len(str(item.get("text", "")))

    return {
        "message_count": len(prepared_messages),
        "role_counts": role_counts,
        "text_messages": text_messages,
        "multimodal_messages": multimodal_messages,
        "total_text_chars": total_text_chars,
    }


def build_disconnect_debug_info(
    request_tag: str,
    model: str,
    timeout_seconds: int,
    prepared_messages: List[dict],
    payload: Dict[str, Any],
    error: Exception,
    elapsed_seconds: float,
) -> Dict[str, Any]:
    return {
        "event": "poe_non_stream_disconnected",
        "timestamp": datetime.now().isoformat(),
        "request_tag": request_tag,
        "model": model,
        "timeout_seconds": timeout_seconds,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "error_type": type(error).__name__,
        "error_message": str(error),
        "payload_keys": sorted(list(payload.keys())),
        "payload_size_chars": _safe_len(json.dumps(payload, ensure_ascii=False)),
        "messages_summary": summarize_messages(prepared_messages),
        "traceback": traceback.format_exc(),
    }


def print_disconnect_debug_info(debug_info: Dict[str, Any]) -> None:
    text = json.dumps(debug_info, ensure_ascii=False, separators=(",", ":"))
    print(f"[POE-DISCONNECT-DEBUG] {text}")