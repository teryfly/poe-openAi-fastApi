from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from auth import verify_api_key
from services.attachments import save_uploads

router = APIRouter()


class UploadedFileItem(BaseModel):
    filename: str
    absolute_path: str
    content_type: Optional[str] = None
    size: int


class UploadFileResponse(BaseModel):
    files: List[UploadedFileItem]


@router.post("/v1/chat/upload-file", response_model=UploadFileResponse)
async def upload_file_api(
    project_name: str = Form(...),
    conversation_name: str = Form(...),
    files: Optional[List[UploadFile]] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
    api_key: str = Depends(verify_api_key),
):
    """
    Supports:
    - single upload by `file`
    - multi upload by `files`
    - or both in same request
    """
    try:
        upload_list: List[UploadFile] = []
        if files:
            upload_list.extend(files)
        if file is not None:
            upload_list.append(file)

        if not upload_list:
            raise HTTPException(status_code=400, detail="No file uploaded")

        saved = save_uploads(
            files=upload_list,
            project_name=project_name,
            conversation_name=conversation_name,
        )

        result = [
            UploadedFileItem(
                filename=original_filename,
                absolute_path=abs_path,
                content_type=content_type,
                size=size,
            )
            for original_filename, abs_path, size, content_type in saved
        ]
        return UploadFileResponse(files=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")