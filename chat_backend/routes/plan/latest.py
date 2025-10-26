from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any
from datetime import datetime
from db import get_conn

router = APIRouter()

def _iso(dt):
    return dt.isoformat() if isinstance(dt, datetime) else dt

def _to_int_or_none(val) -> int:
    """Convert to int or raise 400"""
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid integer: {val}")

def _normalize_sort_by(val) -> str:
    """Normalize sort_by to valid value or raise 400"""
    default = "created_time"
    if val is None or str(val).strip() == "":
        return default
    s = str(val).strip()
    allowed = {"filename", "created_time", "version"}
    if s not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {s}. Must be one of: {allowed}")
    return s

def _normalize_order(val) -> str:
    """Normalize order to asc/desc or raise 400"""
    default = "desc"
    if val is None or str(val).strip() == "":
        return default
    s = str(val).strip().lower()
    if s not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail=f"Invalid order: {s}. Must be 'asc' or 'desc'")
    return s

@router.get("/v1/plan/documents/latest")
async def list_latest_documents(request: Request):
    """
    List latest version of each document in a project.
    Query params (all optional except project_id):
    - project_id: int (required)
    - category_id: int (optional)
    - query: string (filename search)
    - sort_by: filename|created_time|version (default: created_time)
    - order: asc|desc (default: desc)
    - page: int (default: 1)
    - page_size: int (default: 20, max: 200)
    """
    # Extract raw query params without Pydantic validation
    params = dict(request.query_params)
    
    # Parse and validate manually
    pj_id = _to_int_or_none(params.get("project_id"))
    if pj_id is None:
        raise HTTPException(status_code=400, detail="project_id is required")
    
    cat_id = _to_int_or_none(params.get("category_id"))
    
    # Page
    page_raw = params.get("page", "1")
    if str(page_raw).strip() == "":
        page_i = 1
    else:
        try:
            page_i = int(page_raw)
            if page_i < 1:
                page_i = 1
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid page")
    
    # Page size
    page_size_raw = params.get("page_size", "20")
    if str(page_size_raw).strip() == "":
        page_size_i = 20
    else:
        try:
            page_size_i = int(page_size_raw)
            if page_size_i < 1:
                page_size_i = 1
            if page_size_i > 200:
                page_size_i = 200
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid page_size")
    
    # Sort and order
    sort_by_norm = _normalize_sort_by(params.get("sort_by"))
    order_norm = _normalize_order(params.get("order"))
    
    # Query string
    query_raw = params.get("query")
    like = None
    if query_raw is not None:
        q = str(query_raw).strip()
        if q:
            like = f"%{q}%"
    
    # Build WHERE clause
    where = ["pd.project_id=%s"]
    base_params: List[Any] = [pj_id]
    if cat_id is not None:
        where.append("pd.category_id=%s")
        base_params.append(cat_id)
    if like:
        where.append("pd.filename LIKE %s")
        base_params.append(like)
    
    where_sql = " AND ".join(where) if where else "1=1"
    
    # Sort mapping
    sort_map = {
        "filename": "pd.filename",
        "created_time": "pd.created_time",
        "version": "pd.version",
    }
    sort_col = sort_map.get(sort_by_norm, "pd.created_time")
    order_sql = "ASC" if order_norm == "asc" else "DESC"
    
    # SQL queries
    count_sql = f"""
        SELECT COUNT(*) FROM (
            SELECT pd.filename
            FROM plan_documents pd
            JOIN (
                SELECT project_id, category_id, filename, MAX(version) AS max_version
                FROM plan_documents
                WHERE project_id=%s {('AND category_id=%s' if cat_id is not None else '')}
                GROUP BY project_id, category_id, filename
            ) lv ON lv.project_id=pd.project_id
               AND lv.category_id=pd.category_id
               AND lv.filename=pd.filename
               AND lv.max_version=pd.version
            WHERE {where_sql}
            GROUP BY pd.filename
        ) t
    """
    
    data_sql = f"""
        SELECT pd.id, pd.project_id, pd.category_id, pd.filename, pd.content, pd.version,
               pd.source, pd.related_log_id, pd.created_time
        FROM plan_documents pd
        JOIN (
            SELECT project_id, category_id, filename, MAX(version) AS max_version
            FROM plan_documents
            WHERE project_id=%s {('AND category_id=%s' if cat_id is not None else '')}
            GROUP BY project_id, category_id, filename
        ) lv ON lv.project_id=pd.project_id
           AND lv.category_id=pd.category_id
           AND lv.filename=pd.filename
           AND lv.max_version=pd.version
        WHERE {where_sql}
        ORDER BY {sort_col} {order_sql}
        LIMIT %s OFFSET %s
    """
    
    with get_conn() as conn:
        with conn.cursor() as cursor:
            # Count
            try:
                lv_params = [pj_id] + ([cat_id] if cat_id is not None else [])
                count_params = lv_params + base_params
                cursor.execute(count_sql, tuple(count_params))
                total = cursor.fetchone()[0]
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Count failed: {e}")
            
            # Data
            limit = page_size_i
            offset = (page_i - 1) * page_size_i
            
            try:
                data_params = lv_params + base_params + [limit, offset]
                cursor.execute(data_sql, tuple(data_params))
                rows = cursor.fetchall()
                cols = [c[0] for c in cursor.description]
                items: List[Dict[str, Any]] = []
                for row in rows:
                    d = dict(zip(cols, row))
                    if isinstance(d.get("created_time"), datetime):
                        d["created_time"] = _iso(d["created_time"])
                    items.append(d)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Query failed: {e}")
    
    return {
        "total": total,
        "page": page_i,
        "page_size": page_size_i,
        "items": items
    }