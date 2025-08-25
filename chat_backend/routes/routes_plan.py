from fastapi import APIRouter, Body, Query, Path, HTTPException
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

class PlanDocumentUpdateRequest(BaseModel):
    filename: Optional[str] = None
    content: Optional[str] = None
    source: Optional[Literal['user', 'server', 'chat']] = None

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
            # 查询同名文档的最大version
            cursor.execute("""
                SELECT MAX(version) FROM plan_documents 
                WHERE project_id=%s AND category_id=%s AND filename=%s
            """, (doc.project_id, doc.category_id, doc.filename))
            row = cursor.fetchone()
            max_version = row[0] if row and row[0] is not None else 0
            new_version = max_version + 1
            
            # 永远新增，不删除或覆盖老版本
            cursor.execute("""
                INSERT INTO plan_documents 
                    (project_id, category_id, filename, content, version, source, related_log_id, created_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                doc.project_id,
                doc.category_id,
                doc.filename,
                doc.content,
                new_version,
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

@router.get("/v1/plan/documents/history", response_model=List[PlanDocumentResponse])
async def list_document_history(
    project_id: int = Query(..., description="项目ID"),
    category_id: Optional[int] = Query(None, description="分类ID（可选）"),
    filename: Optional[str] = Query(None, description="文档名（可选）")
):
    """
    兼容性说明：
    - 当提供 project_id、category_id、filename 三者时：完全兼容原API，返回该文档的所有历史版本（按 version DESC）。
    - 当仅提供 project_id 时：返回该项目的所有文档（最新与历史全部，按 created_time DESC）。
    - 当提供 project_id 与 category_id 时：返回该项目下指定分类的所有文档（按 created_time DESC）。
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            if category_id is not None and filename is not None:
                # 完全兼容原API
                cursor.execute("""
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s AND category_id=%s AND filename=%s
                    ORDER BY version DESC
                """, (project_id, category_id, filename))
            elif category_id is not None and filename is None:
                # project_id + category_id
                cursor.execute("""
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s AND category_id=%s
                    ORDER BY created_time DESC, id DESC
                """, (project_id, category_id))
            else:
                # 仅 project_id
                cursor.execute("""
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s
                    ORDER BY created_time DESC, id DESC
                """, (project_id,))
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            result: List[dict] = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                if row_dict.get("created_time") and isinstance(row_dict["created_time"], datetime):
                    row_dict["created_time"] = row_dict["created_time"].isoformat()
                result.append(row_dict)
            return result

# ========== 新增：文档详情查看和编辑API ==========

@router.get("/v1/plan/documents/{document_id}", response_model=PlanDocumentResponse)
async def get_plan_document(document_id: int = Path(...)):
    """
    获取单个文档的详细信息
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents WHERE id=%s
            """, (document_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Document not found")
            
            columns = [col[0] for col in cursor.description]
            row_dict = dict(zip(columns, row))
            if row_dict.get("created_time") and isinstance(row_dict["created_time"], datetime):
                row_dict["created_time"] = row_dict["created_time"].isoformat()
            return row_dict

@router.put("/v1/plan/documents/{document_id}", response_model=PlanDocumentResponse)
async def update_plan_document(
    document_id: int = Path(...),
    doc: PlanDocumentUpdateRequest = Body(...)
):
    """
    更新文档信息，会创建新版本而不是覆盖原有版本
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            # 先获取原文档信息
            cursor.execute("""
                SELECT project_id, category_id, filename, content, version, source, related_log_id
                FROM plan_documents WHERE id=%s
            """, (document_id,))
            original_row = cursor.fetchone()
            if not original_row:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # 构建更新后的数据
            project_id, category_id, orig_filename, orig_content, orig_version, orig_source, orig_related_log_id = original_row
            
            new_filename = doc.filename if doc.filename is not None else orig_filename
            new_content = doc.content if doc.content is not None else orig_content
            new_source = doc.source if doc.source is not None else orig_source
            
            # 查询同名文档的最大version
            cursor.execute("""
                SELECT MAX(version) FROM plan_documents 
                WHERE project_id=%s AND category_id=%s AND filename=%s
            """, (project_id, category_id, new_filename))
            row = cursor.fetchone()
            max_version = row[0] if row and row[0] is not None else 0
            new_version = max_version + 1
            
            # 创建新版本
            cursor.execute("""
                INSERT INTO plan_documents 
                    (project_id, category_id, filename, content, version, source, related_log_id, created_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                project_id,
                category_id,
                new_filename,
                new_content,
                new_version,
                new_source,
                orig_related_log_id
            ))
            
            new_id = cursor.lastrowid
            
            # 返回新创建的文档
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