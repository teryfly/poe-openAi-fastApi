from fastapi import APIRouter, HTTPException, Path, Body
from pydantic import BaseModel
from typing import List, Optional
from db import get_conn
from datetime import datetime
from code_project_reader.api import get_project_document
router = APIRouter()
# ========== 数据模型 ==========
class ProjectCreateRequest(BaseModel):
    name: str
    dev_environment: str
    grpc_server_address: str
    llm_model: Optional[str] = "GPT-4.1"
    llm_url: Optional[str] = "http://43.132.224.225:8000/v1/chat/completions"
    git_work_dir: Optional[str] = "/git_workspace"
    ai_work_dir: Optional[str] = "/aiWorkDir"
class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    dev_environment: Optional[str] = None
    grpc_server_address: Optional[str] = None
    llm_model: Optional[str] = None
    llm_url: Optional[str] = None
    git_work_dir: Optional[str] = None
    ai_work_dir: Optional[str] = None
class ProjectResponse(BaseModel):
    id: int
    name: str
    dev_environment: str
    grpc_server_address: str
    llm_model: Optional[str] = None
    llm_url: Optional[str] = None
    git_work_dir: Optional[str] = None
    ai_work_dir: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
# ========== 工具函数 ==========
def _row_to_dict(cursor, row):
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))
# ========== 路由接口 ==========
@router.get("/v1/projects", response_model=List[ProjectResponse])
async def list_projects():
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM projects ORDER BY updated_time DESC, created_time DESC")
            rows = cursor.fetchall()
            return [_row_to_dict(cursor, row) for row in rows]
@router.get("/v1/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int = Path(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Project not found")
            return _row_to_dict(cursor, row)
@router.post("/v1/projects", response_model=ProjectResponse)
async def create_project(project: ProjectCreateRequest = Body(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO projects (
                        name, dev_environment, grpc_server_address,
                        llm_model, llm_url, git_work_dir, ai_work_dir
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        project.name,
                        project.dev_environment,
                        project.grpc_server_address,
                        project.llm_model,
                        project.llm_url,
                        project.git_work_dir,
                        project.ai_work_dir,
                    ),
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Create project failed: {e}")
            new_id = cursor.lastrowid
            cursor.execute("SELECT * FROM projects WHERE id=%s", (new_id,))
            row = cursor.fetchone()
            return _row_to_dict(cursor, row)
@router.put("/v1/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, project: ProjectUpdateRequest = Body(...)):
    updates = []
    values: List[object] = []
    def add(field_name: str, value):
        if value is not None:
            updates.append(f"{field_name}=%s")
            values.append(value)
    add("name", project.name)
    add("dev_environment", project.dev_environment)
    add("grpc_server_address", project.grpc_server_address)
    add("llm_model", project.llm_model)
    add("llm_url", project.llm_url)
    add("git_work_dir", project.git_work_dir)
    add("ai_work_dir", project.ai_work_dir)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    values.append(project_id)
    with get_conn() as conn:
        with conn.cursor() as cursor:
            try:
                sql = f"UPDATE projects SET {', '.join(updates)} WHERE id=%s"
                cursor.execute(sql, tuple(values))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Update project failed: {e}")
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Project not found")
            cursor.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
            row = cursor.fetchone()
            return _row_to_dict(cursor, row)
@router.delete("/v1/projects/{project_id}")
async def delete_project(project_id: int):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM projects WHERE id=%s", (project_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Project not found")
            return {"message": "Project deleted successfully"}
@router.get("/v1/projects/{project_id}/complete-source-code")
async def get_project_complete_source(project_id: int = Path(...)):
    import os
    os.environ["CODE_PROJECT_DEBUG"] = "1"
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT ai_work_dir FROM projects WHERE id=%s", (project_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Project not found")
            ai_work_dir = row[0]
            try:
                project_path = os.path.abspath(ai_work_dir)
                result = get_project_document(project_path, save_output=False)
                return {"completeSourceCode": result["content"]}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to read source code: {e}")