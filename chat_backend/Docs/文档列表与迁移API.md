# 文档列表与迁移 API

本文件补充三个能力：
1) 标题搜索（仅 filename）+ 最新版本列表视图
2) 分类变更（文档迁移）
3) 文档列表聚合视图（最新版）

---

## 1. 最新版本列表 + 标题搜索

GET /v1/plan/documents/latest
- 描述：在项目或项目+分类下，返回“每个 filename 的最新版本”列表；支持 filename 模糊搜索、分页与排序
- 查询参数：
  - project_id: int 必填 项目ID
  - category_id: int 可选 分类ID；不传表示全项目范围
  - query: string 可选 filename 模糊匹配关键字（LIKE %query%）
  - sort_by: enum("filename","created_time","version") 默认 created_time
  - order: enum("asc","desc") 默认 desc
  - page: int 默认 1，>=1
  - page_size: int 默认 20，1~200
- 响应 200
{
  "total": 35,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 123,
      "project_id": 1,
      "category_id": 5,
      "filename": "API设计规范.md",
      "content": "...（该文件最新版本内容）",
      "version": 7,
      "source": "user",
      "related_log_id": null,
      "created_time": "2025-01-08T10:00:00"
    }
  ]
}

说明：
- items 中的每一项为某个 filename 的“最新版本记录”
- total 统计匹配条件下“去重 filename”的数量

---

## 2. 分类变更（文档迁移）

### 2.1 迁移全历史（从分类A到分类B）

POST /v1/plan/documents/migrate/all-history
- 请求体
{
  "project_id": 1,
  "source_category_id": 5,
  "target_category_id": 6,
  "filename": "API设计规范.md"
}
- 行为：
  - 将 source_category_id 下该 filename 的所有历史版本，按原有顺序拷贝到 target_category_id
  - 在目标分类下延续版本号（按目标中已有同名的 MAX(version)+1 开始递增）
  - 保留源分类数据，不删除
- 响应 200
{
  "message": "Migration completed",
  "migrated_count": 7,
  "target_category_id": 6,
  "filename": "API设计规范.md",
  "start_version": 1,
  "end_version": 7
}

### 2.2 从当前版本起迁移（创建新的目标版本轨道）

POST /v1/plan/documents/migrate/from-current
- 请求体
{
  "document_id": 321,           // 源版本ID
  "target_category_id": 6,      // 目标分类
  "new_filename": "API规范.md",  // 可选；不填沿用原 filename
  "source": "user"              // 可选；覆盖 source 字段
}
- 行为：
  - 读取 document_id 对应记录，复制内容到目标分类，作为 new_filename 的最新版本
  - 新版本号为目标分类下该 new_filename 的 MAX(version)+1
  - 源数据保留不变
- 响应 200（新创建版本的完整记录）
{
  "id": 888,
  "project_id": 1,
  "category_id": 6,
  "filename": "API规范.md",
  "content": "...",
  "version": 1,
  "source": "user",
  "related_log_id": null,
  "created_time": "2025-01-08T10:00:00"
}

---

## 3. 文档列表（按项目/分类聚合视图）

使用 GET /v1/plan/documents/latest 实现“按项目/分类聚合视图（仅最新版本）”：
- 仅项目：传 project_id
- 项目+分类：传 project_id + category_id
- 支持 query=keyword 搜索 filename
- 支持分页与排序