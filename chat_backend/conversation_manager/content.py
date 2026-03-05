import json
from typing import Any, Dict, Tuple


def content_to_text(content: Any) -> str:
    """Convert message content to a plain-text fallback."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif item.get("type") == "image_url":
                    url = item.get("image_url", {})
                    if isinstance(url, dict):
                        url = url.get("url", "")
                    parts.append(f"[IMAGE_URL] {url}")
                elif item.get("type") == "file":
                    file_obj = item.get("file", {})
                    if isinstance(file_obj, dict):
                        name = file_obj.get("filename", "file")
                        parts.append(f"[FILE] {name}")
            else:
                parts.append(str(item))
        return "\n".join([p for p in parts if p]).strip()
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def encode_content(content: Any) -> Tuple[str, str]:
    """
    Return:
    - content_text: readable fallback text
    - content_json: JSON string for structured multimodal content
    """
    text = content_to_text(content)
    if isinstance(content, (list, dict)):
        return text, json.dumps(content, ensure_ascii=False)
    return text, ""


def decode_content(content_text: str, content_json: str) -> Any:
    """Restore structured content if JSON exists, else return plain text."""
    if content_json:
        try:
            return json.loads(content_json)
        except Exception:
            return content_text or ""
    return content_text or ""


def normalize_message_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize DB row to API output shape."""
    row = dict(row)
    row["content"] = decode_content(row.get("content", ""), row.get("content_json", ""))
    row.pop("content_json", None)
    return row