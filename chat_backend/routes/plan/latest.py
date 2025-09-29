from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from db import get_conn

router = APIRouter()

def _iso(dt):
    return dt.isoformat() if isinstance(dt, datetime) else dt

@router.get("/v1/plan/documents/latest")
async def list_latest_documents(
    project_id: int = Query(..., description="项目ID"),
    category_id: Optional[int] = Query(None, description="分类ID（可选；不传表示全项目）"),
    query: Optional[str] = Query(None, description="按 filename 模糊查询，大小写不敏感"),
    sort_by: Literal["filename", "created_time", "version"] = Query("created_time", description="排序字段"),
    order: Literal["asc", "desc"] = Query("desc", description="排序方向"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=200, description="分页大小，1-200")
):
    """
    返回“每个 filename 的最新版本”列表视图，可选按分类筛选，支持 filename 模糊搜索与分页/排序。
    返回字段：与 plan_documents 表相同（为该文件的最新版本记录）。
    """
    like = None
    if query:
        like = f"%{query.strip()}%"

    # 基础条件与参数
    where = ["pd.project_id=%s"]
    params: List[Any] = [project_id]
    if category_id is not None:
        where.append("pd.category_id=%s")
        params.append(category_id)

    if like:
        where.append("pd.filename LIKE %s")
        params.append(like)

    where_sql = " AND ".join(where) if where else "1=1"

    # 排序字段映射
    sort_map = {
        "filename": "pd.filename",
        "created_time": "pd.created_time",
        "version": "pd.version",
    }
    sort_col = sort_map.get(sort_by, "pd.created_time")
    order_sql = "ASC" if order.lower() == "asc" else "DESC"

    # 统计总数（distinct filename）
    count_sql = f"""
        SELECT COUNT(*) FROM (
            SELECT pd.filename
            FROM plan_documents pd
            JOIN (
                SELECT project_id, category_id, filename, MAX(version) AS max_version
                FROM plan_documents
                WHERE project_id=%s {('AND category_id=%s' if category_id is not None else '')}
                GROUP BY project_id, category_id, filename
            ) lv ON lv.project_id=pd.project_id
               AND lv.category_id=pd.category_id
               AND lv.filename=pd.filename
               AND lv.max_version=pd.version
            WHERE {where_sql}
            GROUP BY pd.filename
        ) t
    """

    # 数据查询：最新版本记录集合
    data_sql = f"""
        SELECT pd.id, pd.project_id, pd.category_id, pd.filename, pd.content, pd.version,
               pd.source, pd.related_log_id, pd.created_time
        FROM plan_documents pd
        JOIN (
            SELECT project_id, category_id, filename, MAX(version) AS max_version
            FROM plan_documents
            WHERE project_id=%s {('AND category_id=%s' if category_id is not None else '')}
            GROUP BY project_id, category_id, filename
        ) lv ON lv.project_id=pd.project_id
           AND lv.category_id=pd.category_id
           AND lv.filename=pd.filename
           AND lv.max_version=pd.version
        WHERE {where_sql}
        ORDER BY {sort_col} {order_sql}
        LIMIT %s OFFSET %s
    """

    # 构造参数（注意 count 与 data 里内部子查询的条件参数顺序）
    base_params = [project_id] + ([category_id] if category_id is not None else [])
    where_params = [project_id] + ([category_id] if category_id is not None else [])
    if like:
        # where_sql 里包含 LIKE，参数在后面追加
        pass

    with get_conn() as conn:
        with conn.cursor() as cursor:
            # total
            count_params = base_params.copy()
            if like:
                count_params = base_params.copy()  # LIKE 已包含在外层 where，需要追加对应的 where 参数
                # where_sql 使用的是 pd 别名的条件，count_sql 外层 WHERE 使用相同 where_sql
                # 但 count 子查询没有携带 query 参数，需在外层 WHERE 绑定
                # 由于 where_sql 中包含 pd.filename LIKE %s，则此处追加 like 参数
                if category_id is not None:
                    # count_sql: 子查询 group 中也带了 category_id 条件，上面已填充
                    pass
                count_params += ([like] if like else [])
            else:
                # 无 like
                pass

            # 执行 count
            try:
                cursor.execute(count_sql, tuple(count_params))
                total = cursor.fetchone()[0]
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Count failed: {e}")

            # page, offset
            limit = page_size
            offset = (page - 1) * page_size

            # data params
            data_params = base_params.copy()
            if like:
                # 外层 WHERE 的 LIKE 参数
                data_params += [like]
            data_params += [limit, offset]

            try:
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
        "page": page,
        "page_size": page_size,
        "items": items
    }