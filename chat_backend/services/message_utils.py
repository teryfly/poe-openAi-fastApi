from typing import List, Dict, Optional
from config import Config
def is_ignored_user_message(role: str, content: str) -> bool:
    if role.lower() == "user":
        trimmed = (content or "").strip()
        return trimmed in [msg.strip() for msg in Config.ignoredUserMessages]
    return False
def merge_assistant_messages_with_user_history(
    messages: List[Dict],
    user_role: Optional[str] = None,
    user_content: Optional[str] = None,
    ignore_user: bool = False
) -> List[Dict]:
    """
    将连续的assistant消息合并，避免上下文过长。
    保持原messages的顺序，并在需要时附加当前用户消息（当ignore_user为True时仍会把用户内容带入上下文）。
    仅使用 role 和 content 字段，适配 LLM 客户端接口。
    """
    result: List[Dict] = []
    temp_assistant: List[str] = []
    in_msgs = messages + ([{"role": user_role, "content": user_content}] if ignore_user and user_role and user_content else [])
    for msg in in_msgs:
        role = msg.get("role")
        content = msg.get("content", "")
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