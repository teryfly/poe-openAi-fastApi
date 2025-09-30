import os
import uuid
import mimetypes
from typing import Tuple, Dict, Any, List
from fastapi import UploadFile, HTTPException
from config import Config

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def get_allowed_types() -> List[str]:
    raw = (Config.ATTACHMENT_ALLOWED_TYPES or "").strip()
    return [t.strip() for t in raw.split(",") if t.strip()]

def is_allowed_type(mime: str) -> bool:
    if not mime:
        return False
    allowed = get_allowed_types()
    return mime in allowed

def max_size_bytes() -> int:
    return Config.ATTACHMENT_MAX_SIZE_MB * 1024 * 1024

def safe_filename(original_name: str) -> str:
    name, ext = os.path.splitext(original_name)
    ext = ext.lower() if ext else ""
    return f"{uuid.uuid4().hex}{ext}"

def save_upload(file: UploadFile) -> Tuple[str, str, int]:
    """
    保存上传的文件到本地目录，返回 (public_url, saved_path, size)
    """
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if not is_allowed_type(content_type):
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {content_type}")
    ensure_dir(Config.ATTACHMENTS_DIR)
    filename = safe_filename(file.filename or "upload.bin")
    saved_path = os.path.join(Config.ATTACHMENTS_DIR, filename)

    # 流式保存并校验大小
    size = 0
    with open(saved_path, "wb") as f:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_size_bytes():
                try:
                    f.close()
                    os.remove(saved_path)
                except Exception:
                    pass
                raise HTTPException(status_code=413, detail="File too large")
            f.write(chunk)

    # 构建公开URL
    if Config.ATTACHMENT_BASE_URL:
        public_url = f"{Config.ATTACHMENT_BASE_URL.rstrip('/')}/{filename}"
    else:
        public_url = f"/files/{filename}"
    return public_url, saved_path, size

def build_attachment_text_line(url: str, filename: str, content_type: str, size: int) -> str:
    size_kb = round(size / 1024, 1)
    return f"[ATTACHMENT] name={filename} type={content_type} size={size_kb}KB url={url}"

def is_image(mime: str) -> bool:
    return (mime or "").startswith("image/")