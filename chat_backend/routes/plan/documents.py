from fastapi import APIRouter, Body, Query, Path, HTTPException
from typing import Optional, List
from datetime import datetime
from db import get_conn
from .models import (
    PlanDocumentCreateRequest,
    PlanDocumentUpdateRequest,
    PlanDocumentResponse,
    MergeDocumentsRequest,
    MergeDocumentsResponse,
)

router = APIRouter()

def _row_to_dict(cursor, row):
    columns = [c[0] for c in cursor.description]
    return dict(zip(columns, row))

def _iso(dt):
    return dt.isoformat() if isinstance(dt, datetime) else dt

def _to_int_or_none(val: Optional[str]) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid integer: {val}")

@router.post("/v1/plan/documents", response_model=PlanDocumentResponse)
async def create_plan_document(doc: PlanDocumentCreateRequest = Body(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
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
    category_id: Optional[str] = Query(None, description="分类ID（可选；允许空字符串）"),
    filename: Optional[str] = Query(None, description="文档名（可选；允许空字符串）")
):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cat_id = _to_int_or_none(category_id)
            fn = None if filename is None or str(filename).strip() == "" else str(filename).strip()

            if cat_id is not None and fn is not None:
                cursor.execute("""
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s AND category_id=%s AND filename=%s
                    ORDER BY version DESC
                """, (project_id, cat_id, fn))
            elif cat_id is not None and fn is None:
                cursor.execute("""
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s AND category_id=%s
                    ORDER BY created_time DESC, id DESC
                """, (project_id, cat_id))
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
    with get_conn() as conn:
        try:
            conn.begin()
        except Exception:
            pass
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM plan_documents WHERE id=%s", (document_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Document not found")

            removed_refs = removed_logs = removed_tags = removed_docs = 0

            cursor.execute("DELETE FROM document_references WHERE document_id=%s", (document_id,))
            removed_refs = cursor.rowcount

            cursor.execute("DELETE FROM execution_logs WHERE document_id=%s", (document_id,))
            removed_logs = cursor.rowcount

            cursor.execute("DELETE FROM document_tags WHERE document_id=%s", (document_id,))
            removed_tags = cursor.rowcount

            cursor.execute("DELETE FROM plan_documents WHERE id=%s", (document_id,))
            removed_docs = cursor.rowcount

            if removed_docs == 0:
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
    filename = (filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename cannot be empty")

    with get_conn() as conn:
        try:
            conn.begin()
        except Exception:
            pass
        with conn.cursor() as cursor:
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

@router.post("/v1/plan/documents/merge", response_model=MergeDocumentsResponse)
async def merge_documents(body: MergeDocumentsRequest = Body(...)):
    """
    合并文档内容：
    入参：{"document_ids":[...]}
    - 按传入顺序读取每个文档的 filename（作为标题）、version、content
    - 以以下格式拼接，每个文档之间空行分隔：
      --- [文档标题]- 版本[文档版本] 开始 ---
      [文档内容]
      --- [文档标题]- 版本[文档版本] 结束 ---
    返回：{"count": n, "merged": "..."}
    """
    ids = body.document_ids or []
    # 规范化与去重但保留顺序
    cleaned: List[int] = []
    for x in ids:
        try:
            xi = int(x)
            if xi > 0 and xi not in cleaned:
                cleaned.append(xi)
        except Exception:
            continue
    if not cleaned:
        raise HTTPException(status_code=400, detail="document_ids cannot be empty")

    placeholders = ",".join(["%s"] * len(cleaned))
    order_field = ",".join(["%s"] * len(cleaned))  # for FIELD order
    sql = f"""
        SELECT id, filename, version, content
        FROM plan_documents
        WHERE id IN ({placeholders})
        ORDER BY FIELD(id, {order_field})
    """
    params = tuple(cleaned + cleaned)
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                raise HTTPException(status_code=404, detail="Documents not found")
            cols = [c[0] for c in cursor.description]
            parts: List[str] = []
            for row in rows:
                d = dict(zip(cols, row))
                title = (d.get("filename") or "").strip() or f"document_{d.get('id')}"
                version = d.get("version")
                content = d.get("content") or ""
                segment = f"--- {title}- 版本[{version}] 开始 ---\n{content}\n--- {title}- 版本[{version}] 结束 ---"
                parts.append(segment)
            merged_text = "\n\n".join(parts)
            return MergeDocumentsResponse(count=len(parts), merged=merged_text)