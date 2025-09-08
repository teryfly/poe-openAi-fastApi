import os
import uuid
import mimetypes
from typing import Tuple, Dict, Any, List

from fastapi import UploadFile, HTTPException
from config import Config

os.makedirs(Config.ATTACHMENTS_DIR, exist_ok=True)

def _safe_filename(original_name: str) -> str:
    base, ext = os.path.splitext(original_name)
    safe_base = "".join(c for c in base if c.isalnum() or c in ("-", "_"))[:80] or "file"
    ext = ext[:10]
    return f"{safe_base}-{uuid.uuid4().hex}{ext}"

def validate_file(file: UploadFile):
    content_type = (file.content_type or "").lower()
    if Config.ATTACHMENT_ALLOWED_TYPES and content_type not in Config.ATTACHMENT_ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {content_type}")

def save_upload(file: UploadFile) -> Tuple[str, str, int]:
    validate_file(file)
    filename = _safe_filename(file.filename or "upload")
    path = os.path.join(Config.ATTACHMENTS_DIR, filename)
    size = 0
    max_bytes = int(float(Config.ATTACHMENT_MAX_SIZE_MB) * 1024 * 1024)
    with open(path, "wb") as f:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                try:
                    f.close()
                    os.remove(path)
                except Exception:
                    pass
                raise HTTPException(status_code=413, detail=f"File too large (> {Config.ATTACHMENT_MAX_SIZE_MB} MB)")
            f.write(chunk)
    content_type = (file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream")
    return filename, content_type, size

def public_url(filename: str, request_base_url: str) -> str:
    if Config.ATTACHMENT_BASE_URL:
        base = Config.ATTACHMENT_BASE_URL.rstrip("/")
        return f"{base}/{filename}"
    base = request_base_url.rstrip("/")
    return f"{base}/files/{filename}"

def attachments_meta(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "attachments": [
            {
                "filename": f.get("filename"),
                "content_type": f.get("content_type"),
                "size": f.get("size"),
                "url": f.get("url"),
            } for f in files
        ]
    }