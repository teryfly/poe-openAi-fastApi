from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import traceback
from codefileexecutorlib import CodeFileExecutor
from auth import verify_api_key
router = APIRouter()
class WriteSourceCodeRequest(BaseModel):
    root_dir: str
    files_content: str
    log_level: Optional[str] = "INFO"
    backup_enabled: Optional[bool] = True
@router.post("/v1/write-source-code")
async def write_source_code(
    req: WriteSourceCodeRequest = Body(...),
    api_key: str = Depends(verify_api_key)
):
    """
    执行源码写入任务，流式返回每步执行结果。
    """
    try:
        # 校验 root_dir 必须为绝对路径，且存在且可写
        root_dir = os.path.abspath(req.root_dir)
        if not os.path.exists(root_dir):
            raise HTTPException(status_code=400, detail="root_dir does not exist.")
        if not os.path.isdir(root_dir):
            raise HTTPException(status_code=400, detail="root_dir is not a directory.")
        if not os.access(root_dir, os.W_OK):
            raise HTTPException(status_code=400, detail="root_dir is not writable.")
        executor = CodeFileExecutor(
            log_level=req.log_level or "INFO",
            backup_enabled=req.backup_enabled if req.backup_enabled is not None else True
        )
        def result_generator():
            try:
                for stream in executor.codeFileExecutHelper(root_dir, req.files_content):
                    # stream: dict
                    yield stream
            except Exception as e:
                # 捕获所有异常, 以 error 格式返回
                yield {
                    "type": "error",
                    "message": f"Exception: {str(e)}\n{traceback.format_exc()}",
                    "timestamp": "",
                    "data": {}
                }
        # 返回 StreamingResponse
        from fastapi.responses import StreamingResponse
        import json
        async def stream():
            for result in result_generator():
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unhandled exception: {e}")