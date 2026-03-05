import os
import re
import uuid
from typing import List, Tuple

from fastapi import HTTPException, UploadFile
from config import Config


def _safe_segment(name: str, default: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return default
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", raw)
    cleaned = cleaned.strip(" .")
    return cleaned or default


def _base_upload_dir() -> str:
    return os.path.abspath(os.getenv("UPLOAD_ATTACHMENTS_DIR", "upload_attachments"))


def _build_target_dir(project_name: str, conversation_name: str) -> str:
    p = _safe_segment(project_name, "default_project")
    c = _safe_segment(conversation_name, "default_conversation")
    return os.path.join(_base_upload_dir(), p, c)


def _max_size_bytes() -> int:
    return int(getattr(Config, "ATTACHMENT_MAX_SIZE_MB", 20)) * 1024 * 1024


def save_upload(file: UploadFile, project_name: str, conversation_name: str) -> Tuple[str, str, int, str]:
    """
    Save one file to:
    upload_attachments/<project_name>/<conversation_name>/
    Return: (original_filename, absolute_path, size, content_type)
    """
    target_dir = _build_target_dir(project_name, conversation_name)
    os.makedirs(target_dir, exist_ok=True)

    original_name = file.filename or "upload.bin"
    _, ext = os.path.splitext(original_name)
    saved_name = f"{uuid.uuid4().hex}{ext.lower()}"
    abs_path = os.path.abspath(os.path.join(target_dir, saved_name))

    size = 0
    max_size = _max_size_bytes()
    try:
        with open(abs_path, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_size:
                    raise HTTPException(status_code=413, detail="File too large")
                f.write(chunk)
    except HTTPException:
        if os.path.exists(abs_path):
            os.remove(abs_path)
        raise
    except Exception as e:
        if os.path.exists(abs_path):
            os.remove(abs_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    return original_name, abs_path, size, file.content_type or "application/octet-stream"


def save_uploads(files: List[UploadFile], project_name: str, conversation_name: str) -> List[Tuple[str, str, int, str]]:
    """
    Batch save files. If any file fails, previously saved files in this batch are rolled back.
    Return list of:
    (original_filename, absolute_path, size, content_type)
    """
    saved: List[Tuple[str, str, int, str]] = []
    try:
        for f in files:
            saved.append(save_upload(f, project_name=project_name, conversation_name=conversation_name))
        return saved
    except Exception:
        for _, abs_path, _, _ in saved:
            try:
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            except Exception:
                pass
        raise