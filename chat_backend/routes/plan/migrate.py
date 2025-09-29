from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from db import get_conn

router = APIRouter()

class MigrateAllHistoryRequest(BaseModel):
    project_id: int
    source_category_id: int
    target_category_id: int
    filename: str

class MigrateFromCurrentRequest(BaseModel):
    document_id: int
    target_category_id: int
    new_filename: Optional[str] = None  # 可选重命名（迁移后文件名），默认沿用原名
    source: Optional[str] = None        # 可选覆盖 source 字段

@router.post("/v1/plan/documents/migrate/all-history")
async def migrate_all_history(req: MigrateAllHistoryRequest = Body(...)):
    """
    将某个文件（按 project_id+source_category_id+filename）的所有历史版本迁移到 target_category_id。
    若目标分类下已存在同名文件，将继续版本号（延续最大version+1...）。
    行为：
    - 读取源分类同名的全部版本（按 version ASC）
    - 逐条插入到目标分类，同步 content、source、related_log_id、created_time（保留原时间）
    - 新版本号使用目标分类下该 filename 的现有 MAX(version)+1 递增
    - 源数据保留不删除
    返回：迁移条数、新起始版本号、目标文件当前最大版本号
    """
    fn = (req.filename or "").strip()
    if not fn:
        raise HTTPException(status_code=400, detail="filename cannot be empty")
    if req.source_category_id == req.target_category_id:
        raise HTTPException(status_code=400, detail="source and target category cannot be the same")

    with get_conn() as conn:
        with conn.cursor() as cursor:
            # 拉取源历史
            cursor.execute("""
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents
                WHERE project_id=%s AND category_id=%s AND filename=%s
                ORDER BY version ASC
            """, (req.project_id, req.source_category_id, fn))
            rows = cursor.fetchall()
            if not rows:
                raise HTTPException(status_code=404, detail="No source documents found")

            # 目标现有最大版本
            cursor.execute("""
                SELECT COALESCE(MAX(version), 0) FROM plan_documents
                WHERE project_id=%s AND category_id=%s AND filename=%s
            """, (req.project_id, req.target_category_id, fn))
            max_ver = cursor.fetchone()[0] or 0
            start_ver = max_ver + 1
            inserted = 0

            for row in rows:
                # columns 位置：见上方 SELECT 顺序
                _, project_id, _, filename, content, _, source, related_log_id, created_time = row
                max_ver += 1
                cursor.execute("""
                    INSERT INTO plan_documents
                        (project_id, category_id, filename, content, version, source, related_log_id, created_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    project_id, req.target_category_id, filename, content, max_ver,
                    source, related_log_id, created_time
                ))
                inserted += 1

            return {
                "message": "Migration completed",
                "migrated_count": inserted,
                "target_category_id": req.target_category_id,
                "filename": fn,
                "start_version": start_ver,
                "end_version": max_ver
            }

@router.post("/v1/plan/documents/migrate/from-current")
async def migrate_from_current(req: MigrateFromCurrentRequest = Body(...)):
    """
    从指定 document_id 对应文件（按 project_id+category_id+filename）的“下一版本起”
    在 target_category_id 创建一个新的版本轨道：
    - 读取 document_id 的记录，获取 project_id/category_id/filename/content/version/source/related_log_id
    - 允许在目标分类使用 new_filename（未提供则沿用原 filename）
    - 目标新版本 = 目标分类下 new_filename 的 MAX(version)+1
    - 插入一条记录到目标分类，content 同源，source 可覆盖，related_log_id 同源
    - 保留源数据，后续请在目标分类继续追加版本
    返回：新创建的目标文档记录
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT project_id, category_id, filename, content, version, source, related_log_id
                FROM plan_documents WHERE id=%s
            """, (req.document_id,))
            src = cursor.fetchone()
            if not src:
                raise HTTPException(status_code=404, detail="Document not found")

            project_id, _, filename, content, _, source, related_log_id = src
            target_filename = (req.new_filename or filename).strip()
            if not target_filename:
                raise HTTPException(status_code=400, detail="new_filename cannot be empty")

            # 目标文件当前最大版本
            cursor.execute("""
                SELECT COALESCE(MAX(version), 0) FROM plan_documents
                WHERE project_id=%s AND category_id=%s AND filename=%s
            """, (project_id, req.target_category_id, target_filename))
            max_ver = cursor.fetchone()[0] or 0
            new_version = max_ver + 1
            new_source = req.source if req.source is not None else source

            cursor.execute("""
                INSERT INTO plan_documents
                    (project_id, category_id, filename, content, version, source, related_log_id, created_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (project_id, req.target_category_id, target_filename, content, new_version, new_source, related_log_id))

            new_id = cursor.lastrowid
            cursor.execute("""
                SELECT id, project_id, category_id, filename, content, version, source, related_log_id, created_time
                FROM plan_documents WHERE id=%s
            """, (new_id,))
            row = cursor.fetchone()
            cols = [c[0] for c in cursor.description]
            result = dict(zip(cols, row))
            if isinstance(result.get("created_time"), datetime):
                result["created_time"] = result["created_time"].isoformat()
            return result