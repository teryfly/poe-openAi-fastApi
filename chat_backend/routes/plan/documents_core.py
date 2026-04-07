from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query

from db import get_conn
from .documents_shared import iso, row_to_dict, to_int_or_none
from .models import (
    PlanDocumentCreateRequest,
    PlanDocumentResponse,
    PlanDocumentUpdateRequest,
)

router = APIRouter()


@router.post("/v1/plan/documents", response_model=PlanDocumentResponse)
async def create_plan_document(doc: PlanDocumentCreateRequest = Body(...)):
    """Create a new version row for (project_id, category_id, filename)."""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(MAX(version), 0)
                FROM plan_documents
                WHERE project_id=%s AND category_id=%s AND filename=%s
                """,
                (doc.project_id, doc.category_id, doc.filename),
            )
            new_version = (cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                """
                INSERT INTO plan_documents
                    (project_id, category_id, filename, content, version, source, related_log_id, created_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    doc.project_id,
                    doc.category_id,
                    doc.filename,
                    doc.content,
                    new_version,
                    doc.source or "user",
                    doc.related_log_id,
                ),
            )
            new_id = cursor.lastrowid
            cursor.execute(
                """
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents
                WHERE id=%s
                """,
                (new_id,),
            )
            rec = row_to_dict(cursor, cursor.fetchone())
            rec["created_time"] = iso(rec.get("created_time"))
            return rec


@router.get("/v1/plan/documents/history", response_model=List[PlanDocumentResponse])
async def list_document_history(
    project_id: int = Query(..., description="项目ID"),
    category_id: Optional[str] = Query(None, description="分类ID（可选；允许空字符串）"),
    filename: Optional[str] = Query(None, description="文档名（可选；允许空字符串）"),
):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cat_id = to_int_or_none(category_id)
            fn = None if filename is None or str(filename).strip() == "" else str(filename).strip()

            if cat_id is not None and fn is not None:
                cursor.execute(
                    """
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s AND category_id=%s AND filename=%s
                    ORDER BY version DESC
                    """,
                    (project_id, cat_id, fn),
                )
            elif cat_id is not None:
                cursor.execute(
                    """
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s AND category_id=%s
                    ORDER BY created_time DESC, id DESC
                    """,
                    (project_id, cat_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                    FROM plan_documents
                    WHERE project_id=%s
                    ORDER BY created_time DESC, id DESC
                    """,
                    (project_id,),
                )

            out = []
            for row in cursor.fetchall():
                rec = row_to_dict(cursor, row)
                rec["created_time"] = iso(rec.get("created_time"))
                out.append(rec)
            return out


@router.get("/v1/plan/documents/{document_id}", response_model=PlanDocumentResponse)
async def get_plan_document(document_id: int = Path(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents
                WHERE id=%s
                """,
                (document_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Document not found")
            rec = row_to_dict(cursor, row)
            rec["created_time"] = iso(rec.get("created_time"))
            return rec


@router.put("/v1/plan/documents/{document_id}", response_model=PlanDocumentResponse)
async def update_plan_document_in_place(
    document_id: int = Path(...),
    doc: PlanDocumentUpdateRequest = Body(...),
):
    """
    In-place edit:
    - update current row fields directly (no new row)
    """
    updates = []
    values: List[object] = []

    if doc.filename is not None:
        updates.append("filename=%s")
        values.append(doc.filename)
    if doc.content is not None:
        updates.append("content=%s")
        values.append(doc.content)
    if doc.source is not None:
        updates.append("source=%s")
        values.append(doc.source)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    values.append(document_id)

    with get_conn() as conn:
        with conn.cursor() as cursor:
            sql = f"UPDATE plan_documents SET {', '.join(updates)} WHERE id=%s"
            cursor.execute(sql, tuple(values))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Document not found")

            cursor.execute(
                """
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents
                WHERE id=%s
                """,
                (document_id,),
            )
            rec = row_to_dict(cursor, cursor.fetchone())
            rec["created_time"] = iso(rec.get("created_time"))
            return rec


@router.post("/v1/plan/documents/{document_id}", response_model=PlanDocumentResponse)
async def safe_update_plan_document(
    document_id: int = Path(...),
    doc: PlanDocumentUpdateRequest = Body(...),
):
    """
    Safe edit:
    - create new version row with same project/category and optional filename/content/source overrides
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT project_id, category_id, filename, content, source, related_log_id
                FROM plan_documents
                WHERE id=%s
                """,
                (document_id,),
            )
            src = cursor.fetchone()
            if not src:
                raise HTTPException(status_code=404, detail="Document not found")

            project_id, category_id, old_filename, old_content, old_source, related_log_id = src
            new_filename = doc.filename if doc.filename is not None else old_filename
            new_content = doc.content if doc.content is not None else old_content
            new_source = doc.source if doc.source is not None else old_source

            cursor.execute(
                """
                SELECT COALESCE(MAX(version), 0)
                FROM plan_documents
                WHERE project_id=%s AND category_id=%s AND filename=%s
                """,
                (project_id, category_id, new_filename),
            )
            new_version = (cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                """
                INSERT INTO plan_documents
                    (project_id, category_id, filename, content, version, source, related_log_id, created_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    project_id,
                    category_id,
                    new_filename,
                    new_content,
                    new_version,
                    new_source,
                    related_log_id,
                ),
            )
            new_id = cursor.lastrowid

            cursor.execute(
                """
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents
                WHERE id=%s
                """,
                (new_id,),
            )
            rec = row_to_dict(cursor, cursor.fetchone())
            rec["created_time"] = iso(rec.get("created_time"))
            return rec