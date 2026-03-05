import base64
import mimetypes
import os
from typing import Any, Dict, List
from urllib.parse import urlparse


def _is_abs_path(value: str) -> bool:
    if not value:
        return False
    if os.path.isabs(value):
        return True
    return len(value) > 2 and value[1] == ":" and value[2] in ("\\", "/")


def _try_extract_local_path(value: str) -> str:
    if not isinstance(value, str):
        return ""
    v = value.strip()
    if v.startswith("file://"):
        parsed = urlparse(v)
        path = parsed.path or ""
        if len(path) > 2 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        return path
    if _is_abs_path(v):
        return v
    return ""


def file_to_data_url(path: str, mime_hint: str = "") -> str:
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return path
    mime = mime_hint or mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
    with open(abs_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def normalize_content_for_poe(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return content

    normalized: List[Dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type == "text":
            normalized.append({"type": "text", "text": str(item.get("text", ""))})
            continue

        if item_type == "image_url":
            image_obj = item.get("image_url", {})
            if isinstance(image_obj, dict):
                raw_url = str(image_obj.get("url", ""))
            else:
                raw_url = str(image_obj)
            local_path = _try_extract_local_path(raw_url)
            if local_path:
                raw_url = file_to_data_url(local_path, mime_hint="image/*")
            normalized.append({"type": "image_url", "image_url": {"url": raw_url}})
            continue

        if item_type == "file":
            file_obj = item.get("file", {}) if isinstance(item.get("file"), dict) else {}
            filename = str(file_obj.get("filename", "file"))
            file_data = str(file_obj.get("file_data", ""))
            local_path = _try_extract_local_path(file_data)
            if local_path:
                mime = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
                file_data = file_to_data_url(local_path, mime_hint=mime)
            normalized.append({"type": "file", "file": {"filename": filename, "file_data": file_data}})
            continue

        normalized.append(item)

    return normalized


def normalize_messages_for_poe(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for msg in messages:
        normalized.append(
            {
                "role": msg.get("role", "user"),
                "content": normalize_content_for_poe(msg.get("content", "")),
            }
        )
    return normalized