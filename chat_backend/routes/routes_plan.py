from fastapi import APIRouter, Body
from db import get_conn
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime

router = APIRouter()

# ------------------ 分类模型 ------------------

class PlanCategoryModel(BaseModel):
    id: int
    name: str
    prompt_template: str
    message_method: str
    auto_save_category_id: Optional[int] = None
    is_builtin: bool
    created_time: Optional[str] = None  # 修正类型为str

@router.get("/v1/plan/categories", response_model=List[PlanCategoryModel])
async def list_plan_categories():
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, prompt_template, message_method, auto_save_category_id, is_builtin, created_time
                FROM plan_categories
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                if row_dict.get("created_time") and isinstance(row_dict["created_time"], datetime):
                    row_dict["created_time"] = row_dict["created_time"].isoformat()
                result.append(row_dict)
            return result

# ------------------ 文档模型 ------------------
class PlanDocumentCreateRequest(BaseModel):
    project_id: int
    category_id: int
    filename: str
    content: str
    version: Optional[int] = 1
    source: Optional[Literal['user', 'server', 'chat']] = 'user'
    related_log_id: Optional[int] = None

class PlanDocumentResponse(BaseModel):
    id: int
    project_id: int
    category_id: int
    filename: str
    content: str
    version: int
    source: str
    related_log_id: Optional[int]
    created_time: Optional[str] = None  # 修正类型为str

@router.post("/v1/plan/documents", response_model=PlanDocumentResponse)
async def create_plan_document(doc: PlanDocumentCreateRequest = Body(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO plan_documents 
                    (project_id, category_id, filename, content, version, source, related_log_id, created_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                doc.project_id,
                doc.category_id,
                doc.filename,
                doc.content,
                doc.version or 1,
                doc.source or 'user',
                doc.related_log_id
            ))
            new_id = cursor.lastrowid
            cursor.execute("""
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents WHERE id=%s
            """, (new_id,))
            row = cursor.fetchone()
            columns = [col[0] for col in cursor.description]
            row_dict = dict(zip(columns, row))
            if row_dict.get("created_time") and isinstance(row_dict["created_time"], datetime):
                row_dict["created_time"] = row_dict["created_time"].isoformat()
            return row_dict