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

@router.delete("/v1/plan/documents/{document_id}")
async def delete_plan_document(document_id: int = Path(...)):
    """
    删除单个文档版本（按 document_id），并显式统计关联清理数量。
    在一个事务中完成。
    """
    with get_conn() as conn:
        try:
            conn.begin()
        except Exception:
            # autocommit True 下 begin 可能不是必须，但确保事务性
            pass
        with conn.cursor() as cursor:
            # 校验存在
            cursor.execute("SELECT 1 FROM plan_documents WHERE id=%s", (document_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Document not found")

            removed_refs = removed_logs = removed_tags = removed_docs = 0

            # 显式删除关联，便于统计（即使外键可级联）
            cursor.execute("DELETE FROM document_references WHERE document_id=%s", (document_id,))
            removed_refs = cursor.rowcount

            cursor.execute("DELETE FROM execution_logs WHERE document_id=%s", (document_id,))
            removed_logs = cursor.rowcount

            cursor.execute("DELETE FROM document_tags WHERE document_id=%s", (document_id,))
            removed_tags = cursor.rowcount

            # 删除文档本身
            cursor.execute("DELETE FROM plan_documents WHERE id=%s", (document_id,))
            removed_docs = cursor.rowcount

            if removed_docs == 0:
                # 极少数并发情况下被删
                conn.rollback()
                raise HTTPException(status_code=404, detail="Document not found")

            try:
                conn.commit()
            except Exception:
                conn.rollback()
                raise

            return {
                "message": "Document deleted successfully",
                "deleted": {
                    "document_references": removed_refs,
                    "execution_logs": removed_logs,
                    "document_tags": removed_tags,
                    "plan_documents": removed_docs
                }
            }

@router.delete("/v1/plan/documents")
async def delete_all_versions(
    project_id: int = Query(..., description="项目ID"),
    category_id: int = Query(..., description="分类ID"),
    filename: str = Query(..., description="文件名（删除该文件的全部历史版本）")
):
    """
    删除某文件的全部历史版本（按 project_id + category_id + filename），并显式统计关联清理数量。
    在一个事务中完成。
    """
    filename = (filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename cannot be empty")

    with get_conn() as conn:
        try:
            conn.begin()
        except Exception:
            pass
        with conn.cursor() as cursor:
            # 找出所有版本ID
            cursor.execute("""
                SELECT id FROM plan_documents
                WHERE project_id=%s AND category_id=%s AND filename=%s
            """, (project_id, category_id, filename))
            id_rows = cursor.fetchall()
            ids = [r[0] for r in id_rows]

            if not ids:
                conn.rollback()
                raise HTTPException(status_code=404, detail="No documents found")

            removed_refs = removed_logs = removed_tags = removed_docs = 0
            placeholders = ",".join(["%s"] * len(ids))
            ids_tuple = tuple(ids)

            # 显式删除关联（统计数量）
            cursor.execute(
                f"DELETE FROM document_references WHERE document_id IN ({placeholders})",
                ids_tuple
            )
            removed_refs = cursor.rowcount

            cursor.execute(
                f"DELETE FROM execution_logs WHERE document_id IN ({placeholders})",
                ids_tuple
            )
            removed_logs = cursor.rowcount

            cursor.execute(
                f"DELETE FROM document_tags WHERE document_id IN ({placeholders})",
                ids_tuple
            )
            removed_tags = cursor.rowcount

            # 删除文档本身
            cursor.execute(
                f"DELETE FROM plan_documents WHERE id IN ({placeholders})",
                ids_tuple
            )
            removed_docs = cursor.rowcount

            try:
                conn.commit()
            except Exception:
                conn.rollback()
                raise

            return {
                "message": "All versions deleted successfully",
                "deleted": {
                    "document_references": removed_refs,
                    "execution_logs": removed_logs,
                    "document_tags": removed_tags,
                    "plan_documents": removed_docs
                }
            }