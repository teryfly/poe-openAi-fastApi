# 文档列表与搜索（最新版本视图）API（宽容参数版）

GET /v1/plan/documents/latest

说明：
- 返回指定项目（可选分类）下“每个 filename 的最新版本”记录列表
- 支持标题模糊搜索、分页、排序
- 宽容处理：前端可传空字符串（query=、category_id=、page=、page_size=），后端按“未提供”或默认值处理，避免 422

请求参数（Query）：
- project_id: number 必填；支持字符串数字（例如 "41"）
- category_id: number 可选；允许 category_id=（空）或不传；空白将视为未提供
- query: string 可选；允许 query=（空），视为未提供；否则按 filename LIKE %query%
- sort_by: "filename" | "created_time" | "version" 默认 "created_time"
- order: "asc" | "desc" 默认 "desc"
- page: number 默认 1（>=1）；允许 page=（空），按 1 处理
- page_size: number 默认 20（1~200）；允许 page_size=（空），按 20 处理

成功响应 200：
{
  "total": 35,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 123,
      "project_id": 1,
      "category_id": 2,
      "filename": "开发计划.md",
      "content": "（最新版本内容）",
      "version": 7,
      "source": "user",
      "related_log_id": null,
      "created_time": "2025-01-08T10:00:00"
    }
  ]
}

错误响应：
- 400 project_id is required
- 400 Invalid integer: {value} 当 category_id 非法非数字字符串时
- 400 Invalid page | Invalid page_size
- 500 Count failed: ... | Query failed: ...

调用示例：
- 仅项目（无搜索）：
GET /v1/plan/documents/latest?project_id=41

- 项目 + 分类 + 搜索 + 排序 + 分页：
GET /v1/plan/documents/latest?project_id=41&category_id=2&query=计划&page=1&page_size=20&sort_by=created_time&order=desc

- 前端传空字符串参数（均被宽容处理）：
GET /v1/plan/documents/latest?project_id=41&category_id=&query=&page=&page_size=
# 行为等同于：
GET /v1/plan/documents/latest?project_id=41