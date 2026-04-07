from typing import List

from fastapi import APIRouter, Body, HTTPException, Path, Query

from db import get_conn
from .models import MergeDocumentsRequest, MergeDocumentsResponse

router = APIRouter()


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
                    "plan_documents": removed_docs,
                },
            }


@router.delete("/v1/plan/documents")
async def delete_all_versions(
    project_id: int = Query(..., description="项目ID"),
    category_id: int = Query(..., description="分类ID"),
    filename: str = Query(..., description="文件名（删除该文件的全部历史版本）"),
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
            cursor.execute(
                """
                SELECT id FROM plan_documents
                WHERE project_id=%s AND category_id=%s AND filename=%s
                """,
                (project_id, category_id, filename),
            )
            ids = [r[0] for r in cursor.fetchall()]
            if not ids:
                conn.rollback()
                raise HTTPException(status_code=404, detail="No documents found")

            placeholders = ",".join(["%s"] * len(ids))
            ids_tuple = tuple(ids)

            cursor.execute(f"DELETE FROM document_references WHERE document_id IN ({placeholders})", ids_tuple)
            removed_refs = cursor.rowcount

            cursor.execute(f"DELETE FROM execution_logs WHERE document_id IN ({placeholders})", ids_tuple)
            removed_logs = cursor.rowcount

            cursor.execute(f"DELETE FROM document_tags WHERE document_id IN ({placeholders})", ids_tuple)
            removed_tags = cursor.rowcount

            cursor.execute(f"DELETE FROM plan_documents WHERE id IN ({placeholders})", ids_tuple)
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
                    "plan_documents": removed_docs,
                },
            }


@router.post("/v1/plan/documents/merge", response_model=MergeDocumentsResponse)
async def merge_documents(body: MergeDocumentsRequest = Body(...)):
    ids = body.document_ids or []
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
    order_field = ",".join(["%s"] * len(cleaned))
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
                rec = dict(zip(cols, row))
                title = (rec.get("filename") or "").strip() or f"document_{rec.get('id')}"
                version = rec.get("version")
                content = rec.get("content") or ""
                parts.append(
                    f"--- {title}- 版本[{version}] 开始 ---\n{content}\n--- {title}- 版本[{version}] 结束 ---"
                )

            return MergeDocumentsResponse(count=len(parts), merged="\n\n".join(parts))