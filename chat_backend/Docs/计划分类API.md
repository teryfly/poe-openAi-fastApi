# 计划分类 API 文档

本文档整理了“计划（文档）分类”的完整 REST API，包括列表、详情、创建、更新与删除（级联删除关联数据）。

基础路径前缀：无（同服务根路径）

- 返回时间字段均为 ISO8601 字符串
- 错误统一返回格式：{"detail": "错误描述"}

---

## 1. 获取分类列表

GET /v1/plan/categories

- 说明：按 id 升序返回所有分类
- 响应 200

[
  {
    "id": 1,
    "name": "需求计划",
    "prompt_template": "模板内容",
    "message_method": "PlanGetRequest",
    "auto_save_category_id": null,
    "is_builtin": true,
    "created_time": "2025-01-01T10:00:00"
  }
]

---

## 2. 获取单个分类详情

GET /v1/plan/categories/{category_id}

- 路径参数
  - category_id: int 分类ID
- 响应 200

{
  "id": 2,
  "name": "开发计划",
  "prompt_template": "模板内容",
  "message_method": "PlanExecuteRequest",
  "auto_save_category_id": null,
  "is_builtin": false,
  "created_time": "2025-01-02T10:00:00"
}

- 404 Category not found

---

## 3. 创建分类

POST /v1/plan/categories

- 请求体

{
  "name": "测试计划",
  "prompt_template": "模板内容",
  "message_method": "PlanExecuteRequest",
  "auto_save_category_id": null,
  "is_builtin": false
}

- 字段说明
  - name: string 必填，分类名（唯一）
  - prompt_template: string 必填，提示模板
  - message_method: string 必填，对应处理方法名称
  - auto_save_category_id: int|null 可选，自动保存的分类ID（可为 null）
  - is_builtin: boolean 可选，是否内置，默认 false

- 响应 200（创建后的完整对象）

{
  "id": 3,
  "name": "测试计划",
  "prompt_template": "模板内容",
  "message_method": "PlanExecuteRequest",
  "auto_save_category_id": null,
  "is_builtin": false,
  "created_time": "2025-01-03T10:00:00"
}

- 400 Create category failed: ...

---

## 4. 更新分类

PUT /v1/plan/categories/{category_id}

- 路径参数
  - category_id: int 分类ID

- 请求体（所有字段可选，提供即更新）
  - 特殊约定：若需将 auto_save_category_id 置为 NULL，请传 -1

{
  "name": "测试计划（更新）",
  "prompt_template": "新模板",
  "message_method": "PlanGetRequest",
  "auto_save_category_id": -1,
  "is_builtin": true
}

- 响应 200（更新后的完整对象）

{
  "id": 3,
  "name": "测试计划（更新）",
  "prompt_template": "新模板",
  "message_method": "PlanGetRequest",
  "auto_save_category_id": null,
  "is_builtin": true,
  "created_time": "2025-01-03T10:00:00"
}

- 400 No fields provided for update | Update category failed: ...
- 404 Category not found

---

## 5. 删除分类（级联删除相关文档与数据）

DELETE /v1/plan/categories/{category_id}

- 路径参数
  - category_id: int 分类ID

- 行为说明
  1) 查出该分类下的所有文档 plan_documents.id
  2) 依次删除与这些文档关联的数据：
     - document_references（项目/会话引用关系）
     - execution_logs（执行日志）
     - document_tags（标签）
  3) 删除这些文档 plan_documents
  4) 最后删除分类 plan_categories
  注：即使数据库存在外键级联删除，本接口也显式清理，确保一致性与可观察的删除数量反馈。

- 响应 200

{
  "message": "Category and related documents deleted successfully",
  "deleted": {
    "document_references": 5,
    "execution_logs": 12,
    "document_tags": 9,
    "plan_documents": 3
  }
}

- 404 Category not found

---

## 模型定义

PlanCategoryModel
- id: int
- name: string
- prompt_template: string
- message_method: string
- auto_save_category_id: int|null
- is_builtin: bool
- created_time: string|null

PlanCategoryCreateRequest
- name: string
- prompt_template: string
- message_method: string
- auto_save_category_id: int|null
- is_builtin: bool（默认 false）

PlanCategoryUpdateRequest
- name?: string
- prompt_template?: string
- message_method?: string
- auto_save_category_id?: int|null（置空请传 -1）
- is_builtin?: bool