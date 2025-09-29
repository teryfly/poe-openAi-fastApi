from fastapi import APIRouter, Body, Path, Query, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from db import get_conn
from .models import PlanDocumentResponse

router = APIRouter()

# --------- Models ---------
class TagModel(BaseModel):
    id: int
    document_id: int
    tag_name: str
    created_time: Optional[str] = None

class TagCreateRequest(BaseModel):
    tag_name: str = Field(..., description="Tag name (<=100 chars)")

    @field_validator("tag_name")
    @classmethod
    def validate_tag_name(cls, v: str) -> str:
        if v is None:
            raise ValueError("tag_name is required")
        v = v.strip()
        if not v:
            raise ValueError("tag_name cannot be empty")
        if len(v) > 100:
            raise ValueError("tag_name length must be <= 100")
        return v

class TagBatchUpdateRequest(BaseModel):
    add: Optional[List[str]] = Field(default=None, description="Tags to add")
    remove: Optional[List[str]] = Field(default=None, description="Tags to remove")

    @field_validator("add")
    @classmethod
    def validate_add(cls, v):
        if v is None:
            return None
        cleaned: List[str] = []
        for t in v:
            if t is None:
                continue
            s = str(t).strip()
            if not s:
                continue
            if len(s) > 100:
                s = s[:100]
            if s not in cleaned:
                cleaned.append(s)
        return cleaned or None

    @field_validator("remove")
    @classmethod
    def validate_remove(cls, v):
        if v is None:
            return None
        cleaned: List[str] = []
        for t in v:
            if t is None:
                continue
            s = str(t).strip()
            if not s:
                continue
            if len(s) > 100:
                s = s[:100]
            if s not in cleaned:
                cleaned.append(s)
        return cleaned or None

class TagListResponse(BaseModel):
    document_id: int
    tags: List[TagModel]

# --------- Helpers ---------
def _row_to_dict(cursor, row):
    cols = [c[0] for c in cursor.description]
    return dict(zip(cols, row))

def _iso(dt):
    return dt.isoformat() if isinstance(dt, datetime) else dt

def _ensure_document_exists(document_id: int):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM plan_documents WHERE id=%s", (document_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Document not found")

def _fetch_tag_by_unique(document_id: int, tag_name: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, document_id, tag_name, created_time FROM document_tags WHERE document_id=%s AND tag_name=%s",
                (document_id, tag_name)
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = _row_to_dict(cursor, row)
            d["created_time"] = _iso(d.get("created_time"))
            return d

# --------- Routes ---------
@router.get("/v1/plan/documents/{document_id}/tags", response_model=TagListResponse)
async def list_document_tags(document_id: int = Path(...)):
    _ensure_document_exists(document_id)
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, document_id, tag_name, created_time FROM document_tags WHERE document_id=%s ORDER BY tag_name ASC",
                (document_id,)
            )
            rows = cursor.fetchall()
            tags: List[Dict[str, Any]] = []
            for row in rows:
                d = _row_to_dict(cursor, row)
                d["created_time"] = _iso(d.get("created_time"))
                tags.append(d)
            return TagListResponse(document_id=document_id, tags=tags)

@router.post("/v1/plan/documents/{document_id}/tags")
async def add_document_tag(
    document_id: int = Path(...),
    body: TagCreateRequest = Body(...)
):
    _ensure_document_exists(document_id)
    tag_name = body.tag_name
    with get_conn() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO document_tags (document_id, tag_name, created_time) VALUES (%s, %s, NOW())",
                    (document_id, tag_name)
                )
                new_id = cursor.lastrowid
                cursor.execute(
                    "SELECT id, document_id, tag_name, created_time FROM document_tags WHERE id=%s",
                    (new_id,)
                )
                row = cursor.fetchone()
                d = _row_to_dict(cursor, row)
                d["created_time"] = _iso(d.get("created_time"))
                return {
                    "message": "Tag added",
                    "tag": d
                }
            except Exception as e:
                msg = str(e)
                if "Duplicate entry" in msg or "unique_doc_tag" in msg:
                    # treat as idempotent success: fetch existing
                    existing = _fetch_tag_by_unique(document_id, tag_name)
                    return {
                        "message": "Tag added",
                        "tag": existing
                    }
                raise HTTPException(status_code=400, detail=f"Failed to add tag: {e}")

@router.delete("/v1/plan/documents/{document_id}/tags/{tag_name}")
async def remove_document_tag(
    document_id: int = Path(...),
    tag_name: str = Path(...)
):
    _ensure_document_exists(document_id)
    tag_name = (tag_name or "").strip()
    if not tag_name:
        raise HTTPException(status_code=400, detail="tag_name cannot be empty")
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM document_tags WHERE document_id=%s AND tag_name=%s",
                (document_id, tag_name)
            )
            removed = cursor.rowcount
            return {"message": "Tag removed", "removed_count": removed}

@router.post("/v1/plan/documents/{document_id}/tags:batch")
async def batch_update_tags(
    document_id: int = Path(...),
    body: TagBatchUpdateRequest = Body(...)
):
    _ensure_document_exists(document_id)
    add_list = body.add or []
    remove_list = body.remove or []
    if not add_list and not remove_list:
        raise HTTPException(status_code=400, detail="add and remove cannot both be empty")

    added = 0
    duplicates = 0
    removed = 0

    with get_conn() as conn:
        with conn.cursor() as cursor:
            # add
            for tag in add_list:
                try:
                    cursor.execute(
                        "INSERT INTO document_tags (document_id, tag_name, created_time) VALUES (%s, %s, NOW())",
                        (document_id, tag)
                    )
                    added += 1
                except Exception as e:
                    if "Duplicate entry" in str(e) or "unique_doc_tag" in str(e):
                        duplicates += 1
                    else:
                        raise HTTPException(status_code=400, detail=f"Failed to add tag '{tag}': {e}")
            # remove
            if remove_list:
                placeholders = ",".join(["%s"] * len(remove_list))
                cursor.execute(
                    f"DELETE FROM document_tags WHERE document_id=%s AND tag_name IN ({placeholders})",
                    tuple([document_id] + remove_list)
                )
                removed = cursor.rowcount

    return {
        "message": "Tags updated",
        "added": {"requested": len(add_list), "added": added, "duplicates": duplicates},
        "removed": {"requested": len(remove_list), "removed": removed}
    }

@router.get("/v1/plan/documents/search-by-tags", response_model=List[PlanDocumentResponse])
async def search_documents_by_tags(
    project_id: int = Query(..., description="Project ID"),
    tags: str = Query(..., description="Comma separated tag names"),
    match: str = Query("any", pattern="^(any|all)$", description="Match mode: any|all")
):
    # validate input
    tags_list = [t.strip()[:100] for t in (tags or "").split(",") if t.strip()]
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    if not tags_list:
        raise HTTPException(status_code=400, detail="tags cannot be empty")
    mode_all = (match or "any").lower() == "all"

    with get_conn() as conn:
        with conn.cursor() as cursor:
            # Latest version per project/category/filename within project
            # Then join tags on document id
            tag_placeholders = ",".join(["%s"] * len(tags_list))
            base_latest_sql = """
                SELECT pd.*
                FROM plan_documents pd
                JOIN (
                    SELECT project_id, category_id, filename, MAX(version) AS max_version
                    FROM plan_documents
                    WHERE project_id=%s
                    GROUP BY project_id, category_id, filename
                ) lv ON lv.project_id=pd.project_id
                   AND lv.category_id=pd.category_id
                   AND lv.filename=pd.filename
                   AND lv.max_version=pd.version
                JOIN document_tags dt ON dt.document_id = pd.id
                WHERE dt.tag_name IN ({tags})
            """.replace("{tags}", tag_placeholders)

            if mode_all:
                sql = base_latest_sql + " GROUP BY pd.id HAVING COUNT(DISTINCT dt.tag_name) = %s"
                params = tuple([project_id] + tags_list + [len(tags_list)])
            else:
                sql = base_latest_sql + " GROUP BY pd.id"
                params = tuple([project_id] + tags_list)

            try:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                result: List[Dict[str, Any]] = []
                for row in rows:
                    d = _row_to_dict(cursor, row)
                    if isinstance(d.get("created_time"), datetime):
                        d["created_time"] = d["created_time"].isoformat()
                    result.append(d)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Search failed: {e}")