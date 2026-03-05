from typing import Any, Dict, List, Optional
from config import Config


def is_ignored_user_message(role: str, content: Any) -> bool:
    if (role or "").lower() != "user":
        return False
    if not isinstance(content, str):
        return False
    trimmed = content.strip()
    return trimmed in [msg.strip() for msg in Config.ignoredUserMessages]


def merge_assistant_messages_with_user_history(
    messages: List[Dict[str, Any]],
    user_role: Optional[str] = None,
    user_content: Optional[Any] = None,
    ignore_user: bool = False,
) -> List[Dict[str, Any]]:
    """
    Merge consecutive assistant text-only messages.
    Structured assistant messages (list/dict) are not merged.
    """
    in_msgs = list(messages)
    if ignore_user and user_role and user_content is not None:
        in_msgs.append({"role": user_role, "content": user_content})

    result: List[Dict[str, Any]] = []
    assistant_buffer: List[str] = []

    def flush_buffer():
        nonlocal assistant_buffer
        if assistant_buffer:
            result.append({"role": "assistant", "content": "\n---\n".join(assistant_buffer)})
            assistant_buffer = []

    for msg in in_msgs:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "assistant" and isinstance(content, str):
            assistant_buffer.append(content)
            continue

        flush_buffer()
        result.append({"role": role, "content": content})

    flush_buffer()
    return result