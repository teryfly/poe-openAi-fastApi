from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from auth import verify_api_key
from services.attachments import save_upload, build_attachment_text_line, is_image

router = APIRouter()

class UploadFileResponse(BaseModel):
    filename: str
    content_type: Optional[str] = None
    size: int
    url: str
    is_image: bool
    attachment_text_line: str

@router.post("/v1/chat/upload-file", response_model=UploadFileResponse)
async def upload_file_api(
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    """
    单文件上传接口：
    - 接收一个文件，校验类型与大小限制
    - 保存到服务器本地或外部存储（根据配置）
    - 返回可公开访问的 URL 以及一个标准化的附件注入文本行（前端可直接拼接到 user 消息中）
    """
    try:
        url, saved_path, size = save_upload(file)
        ct = file.content_type or ""
        line = build_attachment_text_line(url, file.filename or "file", ct, size)
        return UploadFileResponse(
            filename=file.filename or "",
            content_type=ct,
            size=size,
            url=url,
            is_image=is_image(ct),
            attachment_text_line=line
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")