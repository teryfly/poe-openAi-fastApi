from fastapi import APIRouter, HTTPException, Path, Body
from pydantic import BaseModel
from typing import List, Optional
from db import get_conn  # 确保你有 db.py 里的 get_conn
from datetime import datetime

router = APIRouter()

# ========== 数据模型 ==========
class Project(BaseModel):
    id: Optional[int] = None
    name: str
    dev_environment: str
    grpc_server_address: str
    llm_model: Optional[str] = None
    llm_url: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

# ========== 路由接口 ==========

@router.get("/v1/projects", response_model=List[Project])
async def list_projects():
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM projects ORDER BY id DESC")
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

@router.get("/v1/projects/{project_id}", response_model=Project)
async def get_project(project_id: int = Path(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Project not found")
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))

@router.post("/v1/projects", response_model=Project)
async def create_project(project: Project = Body(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO projects (name, dev_environment, grpc_server_address, llm_model, llm_url)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                project.name,
                project.dev_environment,
                project.grpc_server_address,
                project.llm_model,
                project.llm_url
            ))
            conn.commit()
            project.id = cursor.lastrowid
            cursor.execute("SELECT * FROM projects WHERE id=%s", (project.id,))
            row = cursor.fetchone()
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))

@router.put("/v1/projects/{project_id}", response_model=Project)
async def update_project(project_id: int, project: Project = Body(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE projects SET name=%s, dev_environment=%s, grpc_server_address=%s, 
                    llm_model=%s, llm_url=%s, updated_time=NOW()
                WHERE id=%s
            """, (
                project.name,
                project.dev_environment,
                project.grpc_server_address,
                project.llm_model,
                project.llm_url,
                project_id
            ))
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Project not found")
            cursor.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
            row = cursor.fetchone()
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))

@router.delete("/v1/projects/{project_id}")
async def delete_project(project_id: int):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM projects WHERE id=%s", (project_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Project not found")
            return {"message": "Project deleted successfully"}
