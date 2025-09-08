from fastapi import APIRouter, Body, Path, HTTPException
from typing import List
from datetime import datetime
from db import get_conn
from .models import (
    PlanCategoryModel,
    PlanCategoryCreateRequest,
    PlanCategoryUpdateRequest,
)

router = APIRouter()

def _row_to_dict(cursor, row):
    columns = [c[0] for c in cursor.description]
    return dict(zip(columns, row))

def _iso(dt):
    return dt.isoformat() if isinstance(dt, datetime) else dt

@router.get("/v1/plan/categories", response_model=List[PlanCategoryModel])
async def list_plan_categories():
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, prompt_template, message_method, auto_save_category_id, is_builtin, summary_model, created_time
                FROM plan_categories
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = _row_to_dict(cursor, row)
                d["created_time"] = _iso(d.get("created_time"))
                result.append(d)
            return result

@router.get("/v1/plan/categories/{category_id}", response_model=PlanCategoryModel)
async def get_plan_category(category_id: int = Path(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, prompt_template, message_method, auto_save_category_id, is_builtin, summary_model, created_time
                FROM plan_categories WHERE id=%s
            """, (category_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Category not found")
            d = _row_to_dict(cursor, row)
            d["created_time"] = _iso(d.get("created_time"))
            return d

@router.post("/v1/plan/categories", response_model=PlanCategoryModel)
async def create_plan_category(cat: PlanCategoryCreateRequest = Body(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute("""
                    INSERT INTO plan_categories 
                        (name, prompt_template, message_method, auto_save_category_id, is_builtin, summary_model, created_time)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (
                    cat.name,
                    cat.prompt_template,
                    cat.message_method,
                    cat.auto_save_category_id,
                    bool(cat.is_builtin) if cat.is_builtin is not None else False,
                    cat.summary_model or "GPT-4.1",
                ))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Create category failed: {e}")
            new_id = cursor.lastrowid
            cursor.execute("""
                SELECT id, name, prompt_template, message_method, auto_save_category_id, is_builtin, summary_model, created_time
                FROM plan_categories WHERE id=%s
            """, (new_id,))
            row = cursor.fetchone()
            d = _row_to_dict(cursor, row)
            d["created_time"] = _iso(d.get("created_time"))
            return d

@router.put("/v1/plan/categories/{category_id}", response_model=PlanCategoryModel)
async def update_plan_category(
    category_id: int = Path(...),
    cat: PlanCategoryUpdateRequest = Body(...)
):
    updates: List[str] = []
    values: List[object] = []

    def add(col: str, val):
        if val is not None:
            updates.append(f"{col}=%s")
            values.append(val)

    add("name", cat.name)
    add("prompt_template", cat.prompt_template)
    add("message_method", cat.message_method)

    # auto_save_category_id: -1 表示置空
    if cat.auto_save_category_id == -1:
        updates.append("auto_save_category_id=NULL")
    elif cat.auto_save_category_id is not None:
        updates.append("auto_save_category_id=%s")
        values.append(cat.auto_save_category_id)

    if cat.is_builtin is not None:
        updates.append("is_builtin=%s")
        values.append(bool(cat.is_builtin))

    if cat.summary_model is not None:
        updates.append("summary_model=%s")
        values.append(cat.summary_model)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    values.append(category_id)
    with get_conn() as conn:
        with conn.cursor() as cursor:
            try:
                sql = f"UPDATE plan_categories SET {', '.join(updates)} WHERE id=%s"
                cursor.execute(sql, tuple(values))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Update category failed: {e}")
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Category not found")
            cursor.execute("""
                SELECT id, name, prompt_template, message_method, auto_save_category_id, is_builtin, summary_model, created_time
                FROM plan_categories WHERE id=%s
            """, (category_id,))
            row = cursor.fetchone()
            d = _row_to_dict(cursor, row)
            d["created_time"] = _iso(d.get("created_time"))
            return d

@router.delete("/v1/plan/categories/{category_id}")
async def delete_plan_category(category_id: int = Path(...)):
    """
    删除分类及其关联：
      1) 删除 document_references（通过文档ID）
      2) 删除 execution_logs（通过文档ID）
      3) 删除 document_tags（通过文档ID）
      4) 删除 plan_documents（通过分类ID）
      5) 删除分类
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            # 确认存在
            cursor.execute("SELECT 1 FROM plan_categories WHERE id=%s", (category_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Category not found")

            # 获取该分类的所有文档ID
            cursor.execute("SELECT id FROM plan_documents WHERE category_id=%s", (category_id,))
            doc_ids = [r[0] for r in cursor.fetchall()]

            removed_refs = removed_logs = removed_tags = removed_docs = 0

            if doc_ids:
                placeholders = ",".join(["%s"] * len(doc_ids))
                # 引用
                cursor.execute(
                    f"DELETE FROM document_references WHERE document_id IN ({placeholders})",
                    tuple(doc_ids)
                )
                removed_refs = cursor.rowcount
                # 执行日志
                cursor.execute(
                    f"DELETE FROM execution_logs WHERE document_id IN ({placeholders})",
                    tuple(doc_ids)
                )
                removed_logs = cursor.rowcount
                # 标签
                cursor.execute(
                    f"DELETE FROM document_tags WHERE document_id IN ({placeholders})",
                    tuple(doc_ids)
                )
                removed_tags = cursor.rowcount
                # 文档
                cursor.execute(
                    f"DELETE FROM plan_documents WHERE id IN ({placeholders})",
                    tuple(doc_ids)
                )
                removed_docs = cursor.rowcount

            # 删除分类
            cursor.execute("DELETE FROM plan_categories WHERE id=%s", (category_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Category not found")

            return {
                "message": "Category and related documents deleted successfully",
                "deleted": {
                    "document_references": removed_refs,
                    "execution_logs": removed_logs,
                    "document_tags": removed_tags,
                    "plan_documents": removed_docs
                }
            }