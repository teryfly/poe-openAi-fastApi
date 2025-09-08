from fastapi import APIRouter, Body, Query, Path, HTTPException
from typing import Optional, List
from datetime import datetime
from db import get_conn
from .models import (
    PlanDocumentCreateRequest,
    PlanDocumentUpdateRequest,
    PlanDocumentResponse,
)

router = APIRouter()

def _row_to_dict(cursor, row):
    columns = [c[0] for c in cursor.description]
    return dict(zip(columns, row))

def _iso(dt):
    return dt.isoformat() if isinstance(dt, datetime) else dt

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
            d = _row_to_dict(cursor, row)
            d["created_time"] = _iso(d.get("created_time"))
            return d

@router.get("/v1/plan/documents/history", response_model=List[PlanDocumentResponse])
async def list_document_history(
    project_id: int = Query(..., description="项目ID"),
    category_id: Optional[int] = Query(None, description="分类ID（可选）"),
    filename: Optional[str] = Query(None, description="文档名（可选）")
):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            if category_id is not None and filename is not None:
                cursor.execute("""
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s AND category_id=%s AND filename=%s
                    ORDER BY version DESC
                """, (project_id, category_id, filename))
            elif category_id is not None and filename is None:
                cursor.execute("""
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s AND category_id=%s
                    ORDER BY created_time DESC, id DESC
                """, (project_id, category_id))
            else:
                cursor.execute("""
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s
                    ORDER BY created_time DESC, id DESC
                """, (project_id,))
            rows = cursor.fetchall()
            result: List[dict] = []
            for row in rows:
                d = _row_to_dict(cursor, row)
                d["created_time"] = _iso(d.get("created_time"))
                result.append(d)
            return result

@router.get("/v1/plan/documents/{document_id}", response_model=PlanDocumentResponse)
async def get_plan_document(document_id: int = Path(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents WHERE id=%s
            """, (document_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Document not found")
            d = _row_to_dict(cursor, row)
            d["created_time"] = _iso(d.get("created_time"))
            return d

@router.put("/v1/plan/documents/{document_id}", response_model=PlanDocumentResponse)
async def update_plan_document(
    document_id: int = Path(...),
    doc: PlanDocumentUpdateRequest = Body(...)
):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            # 取原文档
            cursor.execute("""
                SELECT project_id, category_id, filename, content, version, source, related_log_id
                FROM plan_documents WHERE id=%s
            """, (document_id,))
            original_row = cursor.fetchone()
            if not original_row:
                raise HTTPException(status_code=404, detail="Document not found")

            project_id, category_id, orig_filename, orig_content, _, orig_source, orig_related_log_id = original_row

            new_filename = doc.filename if doc.filename is not None else orig_filename
            new_content = doc.content if doc.content is not None else orig_content
            new_source = doc.source if doc.source is not None else orig_source

            cursor.execute("""
                SELECT MAX(version) FROM plan_documents 
                WHERE project_id=%s AND category_id=%s AND filename=%s
            """, (project_id, category_id, new_filename))
            row = cursor.fetchone()
            max_version = row[0] if row and row[0] is not None else 0
            new_version = max_version + 1

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
            cursor.execute("""
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents WHERE id=%s
            """, (new_id,))
            row = cursor.fetchone()
            d = _row_to_dict(cursor, row)
            d["created_time"] = _iso(d.get("created_time"))
            return d