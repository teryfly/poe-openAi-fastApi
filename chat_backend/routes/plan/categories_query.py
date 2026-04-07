from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from db import get_conn
from .models import PlanCategoryModel

router = APIRouter()


def _row_to_dict(cursor, row):
    """将数据库 tuple 行转换为 dict。"""
    columns = [c[0] for c in cursor.description]
    return dict(zip(columns, row))


def _iso(dt):
    """将 datetime 转为 ISO 字符串。"""
    return dt.isoformat() if isinstance(dt, datetime) else dt


@router.get("/v1/plan/categories/by-name", response_model=PlanCategoryModel)
async def get_plan_category_by_name(
    name: str = Query(..., description="分类名称（精确匹配）")
):
    """
    按分类名称精确查询单个分类。
    """
    category_name = (name or "").strip()
    if not category_name:
        raise HTTPException(status_code=400, detail="name cannot be empty")

    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, prompt_template, message_method,
                       auto_save_category_id, is_builtin, summary_model, created_time
                FROM plan_categories
                WHERE name=%s
                LIMIT 1
                """,
                (category_name,),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Category not found")

            result = _row_to_dict(cursor, row)
            result["created_time"] = _iso(result.get("created_time"))
            return result