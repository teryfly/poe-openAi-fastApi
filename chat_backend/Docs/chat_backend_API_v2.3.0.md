# chat_backend API 文档

**版本：** 2.3.0 · 综合整理版  
**Base URL：** `http://{HOST}:{PORT}`（默认端口 8000）  
**认证方式：** HTTP Bearer — `Authorization: Bearer <token>`，token 须以 `sk-test` 或 `poe-sk` 开头

> JSON 编码 UTF-8；时间戳为 ISO 8601 字符串。SSE 流响应 Content-Type: `text/event-stream`。错误统一格式：`{"detail": "错误信息"}`

---

## 一、系统简介

本系统是一个以项目为单位管理 LLM 对话上下文与知识库的后台 API，主要用于管理软件开发的文档与 Vibe Coding 过程。

每个项目下包含：
- 多个会话（Conversation）
- 可分类管理的文档库（计划/知识库）
- 文档可设置为「项目级引用」（对项目下所有会话生效）或「会话级引用」

每个会话中的消息可远程调用 LLM，交互记录落库，系统配套前端供人工监控与干预。发送消息时可调用 `complete-source-code` 端点，将项目工作目录中所有文本/代码文件组装为带层级目录的大文本，作为完整源码上下文一并提交。

---

## 二、API 总览索引

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|:----:|------|
| GET | `/` | — | 根信息 |
| GET | `/health` | — | 健康检查 |
| GET | `/v1/models` | — | 模型列表 |
| POST | `/v1/chat/completions` | ✓ | OpenAI 兼容聊天（支持 SSE / multipart） |
| POST | `/v1/chat/upload-file` | ✓ | 上传附件（单文件或多文件） |
| POST | `/v1/chat/conversations` | — | 创建会话 |
| GET | `/v1/chat/conversations` | — | 会话列表 |
| GET | `/v1/chat/conversations/grouped` | — | 按项目分组会话 |
| GET | `/v1/chat/conversations/{id}` | — | 会话详情 |
| PUT | `/v1/chat/conversations/{id}` | — | 更新会话 |
| DELETE | `/v1/chat/conversations/{id}` | — | 删除会话 |
| GET | `/v1/chat/conversations/{id}/messages` | — | 会话消息列表 |
| POST | `/v1/chat/conversations/{id}/messages` | ✓ | 追加消息并获取 LLM 回复（支持 SSE） |
| GET | `/v1/chat/conversations/{id}/referenced-documents` | — | 查询会话引用的文档（含项目级+会话级） |
| GET | `/v1/chat/conversations/{id}/document-references` | — | 查询会话级引用关系 |
| POST | `/v1/chat/conversations/{id}/document-references` | — | 设置会话级引用（完全替换） |
| DELETE | `/v1/chat/conversations/{id}/document-references` | — | 清空会话级引用 |
| POST | `/v1/chat/messages/delete` | — | 批量删除消息 |
| POST | `/v1/chat/stop-stream` | — | 停止流式会话 |
| GET | `/v1/projects` | — | 项目列表 |
| GET | `/v1/projects/{id}` | — | 项目详情 |
| POST | `/v1/projects` | — | 新建项目 |
| PUT | `/v1/projects/{id}` | — | 更新项目 |
| DELETE | `/v1/projects/{id}` | — | 删除项目 |
| GET | `/v1/projects/{id}/complete-source-code` | — | 聚合工程源码文本 |
| GET | `/v1/projects/{id}/document-references` | — | 查询项目级引用 |
| POST | `/v1/projects/{id}/document-references` | — | 设置项目级引用（完全替换） |
| DELETE | `/v1/projects/{id}/document-references` | — | 清空项目级引用 |
| GET | `/v1/plan/categories` | — | 计划分类列表 |
| GET | `/v1/plan/categories/{id}` | — | 单个分类详情 |
| POST | `/v1/plan/categories` | — | 创建分类 |
| PUT | `/v1/plan/categories/{id}` | — | 更新分类 |
| DELETE | `/v1/plan/categories/{id}` | — | 删除分类（级联） |
| POST | `/v1/plan/documents` | — | 新增文档版本 |
| GET | `/v1/plan/documents/history` | — | 文档历史版本 |
| GET | `/v1/plan/documents/latest` | — | 文档最新版本列表（含搜索/分页） |
| POST | `/v1/plan/documents/merge` | — | 合并多文档内容 |
| POST | `/v1/plan/documents/migrate/all-history` | — | 迁移文档全历史 |
| POST | `/v1/plan/documents/migrate/from-current` | — | 从当前版本起迁移 |
| GET | `/v1/plan/documents/{id}` | — | 文档详情 |
| PUT | `/v1/plan/documents/{id}` | — | 编辑文档（生成新版本） |
| POST | `/v1/write-source-code` | — | 写入源码文件（SSE） |

---

## 三、通用数据对象

### 3.1 Project（项目）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| name | string | 项目名称（唯一） |
| dev_environment | string | 开发环境描述 |
| grpc_server_address | string | 通信/部署服务器地址（可填占位符） |
| llm_model | string | 默认模型，如 GPT-5.2 |
| llm_url | string | LLM 远端地址 |
| git_work_dir | string | Git 工作目录 |
| ai_work_dir | string | 项目文件工作目录根路径 |
| created_time | string | ISO 8601 |
| updated_time | string | ISO 8601 |

### 3.2 Conversation（会话）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string (UUID) | 主键 |
| name | string | 会话名称 |
| system_prompt | string | 系统提示词 |
| model | string | 使用的模型 |
| assistance_role | string | 助手角色描述 |
| status | int | 0=正常，1=存档 |
| project_id | int | 所属项目 ID |
| created_at | string | ISO 8601 |
| updated_at | string | ISO 8601，任意消息变动均会刷新 |

### 3.3 Message（消息）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| conversation_id | string | 所属会话 UUID |
| role | string | user / assistant / system / tool / function |
| content | string 或 array | 消息内容（文字时为字符串，含附件时为结构化数组） |
| created_at | string | ISO 8601 |
| updated_at | string | ISO 8601 |

---

## 四、基础接口

### 4.1 根信息

```
GET /
```

无需鉴权。返回服务信息、版本、当前 LLM 后端与常用端点。

### 4.2 健康检查

```
GET /health
```

```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T10:00:00Z",
  "llm_backend": "openai"
}
```

### 4.3 模型列表

```
GET /v1/models
```

```json
{
  "object": "list",
  "data": [
    { "id": "GPT-5.2", "object": "model", "created": 1714000000, "owned_by": "..." }
  ]
}
```

---

## 五、聊天接口

### 5.1 OpenAI 兼容聊天（纯文字）

```
POST /v1/chat/completions        需要鉴权
Content-Type: application/json
```

**请求字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| model | string | 是 | 模型名称 |
| messages | array | 是 | 消息数组，role 可为 system / user / assistant / tool / function |
| stream | bool | 否 | 默认 false；为 true 时以 SSE 返回 |
| functions/tools | ... | 否 | 原生 OpenAI 字段，透传到 LLM |

**关联已有会话（二选一）：**
- 在最后一条消息的 `name` 字段填写 `"cid-<conversation_id>"`
- （不推荐）在消息对象中添加非标准 `conversation_id` 字段

**非流式响应：** 返回标准 OpenAI JSON，`choices[0].message.content` 包含回答，`usage` 为简易分词统计。

**SSE 流式响应：**
- 逐帧发送 `chat.completion.chunk` 格式数据
- 结束帧含 `finish_reason="stop"`，随后发送 `data: [DONE]`
- 以 `"Thinking..."` 开头的分片会被过滤，不出现在输出与落库记录中

**请求示例：**

```json
{
  "model": "GPT-4.1",
  "stream": true,
  "messages": [
    { "role": "system", "content": "You are helpful." },
    { "role": "user", "content": "Hello" },
    { "role": "user", "content": "继续", "name": "cid-<conversation_id>" }
  ]
}
```

该接口也支持结构化 content（含附件），详见 5.3 节。

---

### 5.2 上传附件

```
POST /v1/chat/upload-file        需要鉴权
Content-Type: multipart/form-data
```

先上传附件取得文件路径，再通过消息接口发送结构化内容（见 5.3 节）。支持单次上传多个文件，也支持多次上传后合并附件一起提问。

**form-data 字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| project_name | string | 是 | 项目名 |
| conversation_name | string | 是 | 会话名 |
| files | File（可重复） | 推荐 | 多文件上传，添加多个同名字段 |
| file | File | 兼容 | 单文件上传（旧方式兼容） |

**响应（200）：**

```json
{
  "files": [
    {
      "filename": "需求说明.pdf",
      "absolute_path": "/abs/path/upload_attachments/项目A/会话1/3f2a....pdf",
      "content_type": "application/pdf",
      "size": 125830
    },
    {
      "filename": "截图.png",
      "absolute_path": "/abs/path/upload_attachments/项目A/会话1/9ab1....png",
      "content_type": "image/png",
      "size": 84521
    }
  ]
}
```

> `absolute_path` 即后续发送消息时填入 `file_data` 或 `image_url.url` 的值，后端会自动将绝对路径转为 Poe 兼容的 `data:` 格式再调用 LLM。

**错误码：**

| 状态码 | 说明 |
|--------|------|
| 401 | Authorization 头无效 |
| 413 | 单文件超过大小限制（默认 20MB，可通过 `ATTACHMENT_MAX_SIZE_MB` 调整） |
| 415 | 文件类型不在白名单（默认支持 image/png, image/jpeg, image/webp, application/pdf） |
| 500 | 保存附件失败 |

---

### 5.3 发送结构化内容（含附件）

上传附件后，通过会话消息接口（推荐）或 completions 接口（可选）发送结构化 `content`，后端会将附件内容持久化到数据库，后续对话自动带入附件历史上下文。

#### 方式一：会话消息接口（推荐）

```
POST /v1/chat/conversations/{conversation_id}/messages        需要鉴权
Content-Type: application/json
```

将 `content` 字段改为数组，混合 `text`、`file`、`image_url` 三种类型：

```json
{
  "role": "user",
  "model": "Claude-Sonnet-4.5",
  "stream": false,
  "content": [
    { "type": "text", "text": "请结合这些附件给出总结和待办项。" },
    {
      "type": "file",
      "file": {
        "filename": "需求说明.pdf",
        "file_data": "/abs/path/upload_attachments/项目A/会话1/3f2a....pdf"
      }
    },
    {
      "type": "file",
      "file": {
        "filename": "排期.xlsx",
        "file_data": "/abs/path/upload_attachments/项目A/会话1/7d91....xlsx"
      }
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "/abs/path/upload_attachments/项目A/会话1/9ab1....png"
      }
    }
  ]
}
```

**content 块类型说明：**

| type | 字段结构 | 适用场景 |
|------|----------|----------|
| `text` | `{ "type": "text", "text": "..." }` | 文字内容 |
| `file` | `{ "type": "file", "file": { "filename": "...", "file_data": "<absolute_path>" } }` | PDF、Excel 等非图片文件 |
| `image_url` | `{ "type": "image_url", "image_url": { "url": "<absolute_path>" } }` | 图片文件 |

#### 方式二：completions 接口（可选）

使用 `POST /v1/chat/completions`，在消息中设置 `name: "cid-{conversation_id}"` 关联会话，后端同样会将结构化附件内容与回复持久化：

```json
{
  "model": "Claude-Sonnet-4.5",
  "stream": false,
  "messages": [
    {
      "role": "user",
      "name": "cid-8b7f3c2a-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "content": [
        { "type": "text", "text": "请分析全部附件" },
        {
          "type": "file",
          "file": {
            "filename": "report.pdf",
            "file_data": "/abs/path/upload_attachments/项目A/会话1/3f2a....pdf"
          }
        }
      ]
    }
  ]
}
```

---

### 5.4 多次上传 + 一次提问（推荐流程）

**步骤：**

1. 第一次调用 `/v1/chat/upload-file`，将返回的 `files[]` 存入前端状态（如 `uploadedAttachments`）
2. 第二次、第三次上传，将新返回的 `files[]` 继续追加到 `uploadedAttachments`
3. 发起提问时，将所有已上传附件一次性组装进 `content` 数组

**前端示例代码：**

```javascript
const uploadedAttachments = [];

// 上传函数（可多次调用）
async function uploadBatch(files, token, projectName, conversationName) {
  const fd = new FormData();
  fd.append("project_name", projectName);
  fd.append("conversation_name", conversationName);
  files.forEach((f) => fd.append("files", f));

  const resp = await fetch("/v1/chat/upload-file", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd
  });
  if (!resp.ok) throw new Error("upload failed");
  const data = await resp.json();
  uploadedAttachments.push(...(data.files || []));
}

// 提问函数（把历史上传的附件全部带上）
async function askWithAllUploadedAttachments(conversationId, token, questionText) {
  const content = [{ type: "text", text: questionText }];

  for (const f of uploadedAttachments) {
    if ((f.content_type || "").startsWith("image/")) {
      content.push({
        type: "image_url",
        image_url: { url: f.absolute_path }
      });
    } else {
      content.push({
        type: "file",
        file: {
          filename: f.filename,
          file_data: f.absolute_path
        }
      });
    }
  }

  const resp = await fetch(`/v1/chat/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      role: "user",
      model: "Claude-Sonnet-4.5",
      stream: false,
      content
    })
  });
  if (!resp.ok) throw new Error("ask failed");
  return resp.json();
}
```

---

## 六、会话管理

### 6.1 创建会话

```
POST /v1/chat/conversations
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| project_id | int | 否 | 默认 0 |
| name | string | 否 | 会话名称 |
| system_prompt | string | 否 | 系统提示词 |
| model | string | 否 | 指定模型 |
| assistance_role | string | 否 | 助手角色描述 |
| status | int | 否 | 0=正常（默认），1=存档 |

响应：`{ "conversation_id": "uuid" }`

### 6.2 会话列表

```
GET /v1/chat/conversations?project_id={int}&status={int}
```

响应：Conversation 数组，含 status / updated_at 等字段。

### 6.3 按项目分组

```
GET /v1/chat/conversations/grouped
```

响应：以 project_id 为 key 的 Conversation 数组字典。

### 6.4 会话详情

```
GET /v1/chat/conversations/{conversation_id}
```

响应：Conversation 或 404。

### 6.5 更新会话

```
PUT /v1/chat/conversations/{conversation_id}
```

请求体字段均可选：`project_id`、`name`、`model`、`assistance_role`、`status`。

响应：`{ "message": "Conversation updated" }` 或 404。

### 6.6 删除会话

```
DELETE /v1/chat/conversations/{conversation_id}
```

响应：`{ "message": "Conversation deleted" }` 或 404。

---

## 七、消息管理

### 7.1 获取消息列表

```
GET /v1/chat/conversations/{conversation_id}/messages
```

响应：`{ "conversation_id": "...", "messages": [Message, ...] }` 或 404。

---

### 7.2 追加消息并获取 LLM 回复

```
POST /v1/chat/conversations/{conversation_id}/messages        需要鉴权
Content-Type: application/json
```

**请求体：**

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|:----:|------|------|
| role | string | 是 | — | user / assistant / ... |
| content | string 或 array | 是 | — | 纯文字时传字符串；含附件时传结构化数组（见第五章） |
| model | string | 否 | ChatGPT-4o-Latest | 使用的模型 |
| stream | bool | 否 | false | 是否 SSE 流式返回 |
| documents | int[] | 否 | — | plan_documents 的 id 数组，用于临时注入知识库文档到本次上下文（见下方说明） |

> **documents 字段说明：** 传入后，系统按 id 查询各文档的 filename 与 content，在提交 LLM 前追加到本次会话 system prompt 之后，格式为：
>
> ```
> ----- {filename} BEGINE -----
> {content}
> ----- {filename} END -----
> ```
>
> 仅影响本次请求，不持久化。与「文档引用」机制不同——引用关系是持久的，`documents` 字段是一次性临时注入。

**非流式响应：**

```json
{
  "conversation_id": "uuid",
  "reply": "助手回复内容",
  "user_message_id": 123,
  "assistant_message_id": 124
}
```

**SSE 流式响应：**
- 首帧：`{ "user_message_id": int|null, "assistant_message_id": int, "conversation_id": "...", "session_id": "..." }`
- 多帧：`{ "content": "partial text" }`
- 完成：`{ "content": "", "finish_reason": "stop" }` + `data: [DONE]`

**忽略用户消息策略：** 若 `role=user` 且 `content` 完全匹配 `Config.ignoredUserMessages`，该消息不会入库，但仍可带入上下文。

---

### 7.3 批量删除消息

```
POST /v1/chat/messages/delete
```

请求体：`{ "message_ids": [int, ...] }`

响应：`{ "message": "{n} messages deleted" }`

### 7.4 停止流式会话

```
POST /v1/chat/stop-stream
```

请求体：`{ "session_id": "..." }`

响应：`{ "message": "Stream stopped", "session_id": "..." }`

---

## 八、项目管理

### 8.1 项目列表

```
GET /v1/projects
```

响应：Project 数组。

### 8.2 项目详情

```
GET /v1/projects/{id}
```

响应：Project 或 404。

### 8.3 新建项目

```
POST /v1/projects
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|:----:|------|------|
| name | string | 是 | — | 项目名称，全局唯一 |
| dev_environment | string | 是 | — | 开发环境描述，用于上下文提示 |
| grpc_server_address | string | 是 | — | 通信/部署服务器地址，不使用可填占位符 |
| llm_model | string | 否 | GPT-5.2 | 默认模型（实际调用通常显式指定） |
| llm_url | string | 否 | http://43.132.224.225:8000/v1/chat/completions | LLM 远端地址 |
| git_work_dir | string | 否 | /git_workspace | 本地临时 Git 提交目录 |
| ai_work_dir | string | 否 | /aiWorkDir | 项目文件工作目录根路径 |

**请求示例：**

```json
{
  "name": "demo",
  "dev_environment": "python3.11",
  "grpc_server_address": "192.168.120.238:50051",
  "llm_model": "GPT-4.1",
  "llm_url": "http://43.132.224.225:8000/v1/chat/completions",
  "git_work_dir": "/git_workspace",
  "ai_work_dir": "/aiWorkDir"
}
```

响应：新建的 Project（含 created_time / updated_time）。

### 8.4 更新项目

```
PUT /v1/projects/{id}
```

请求体字段均可选（同新建项目字段）。响应：更新后的 Project 或 404。

### 8.5 删除项目

```
DELETE /v1/projects/{id}
```

响应：`{ "message": "Project deleted successfully" }` 或 404。

### 8.6 获取完整源码文本

```
GET /v1/projects/{id}/complete-source-code
```

依赖 `code_project_reader` 与数据库中 `ai_work_dir` 路径。

响应：`{ "completeSourceCode": "<带层级目录的大文本>" }`

---

## 九、计划分类管理

> 分类（Category）是文档库的组织单元，每个分类下包含多个版本文档。`category_id=5` 为知识库专用分类。

### 9.1 分类对象字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| name | string | 分类名称（唯一） |
| prompt_template | string | 提示模板 |
| message_method | string | 处理方法名称，如 PlanGetRequest / PlanExecuteRequest |
| auto_save_category_id | int\|null | 自动保存的目标分类 ID |
| is_builtin | bool | 是否内置分类 |
| summary_model | string | 总结/生成时默认使用的模型（默认 GPT-4.1） |
| created_time | string | ISO 8601 |

### 9.2 获取分类列表

```
GET /v1/plan/categories
```

按 id 升序返回所有分类。

### 9.3 获取单个分类详情

```
GET /v1/plan/categories/{category_id}
```

响应：分类对象或 404。

### 9.4 创建分类

```
POST /v1/plan/categories
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| name | string | 是 | 分类名称，唯一 |
| prompt_template | string | 是 | 提示模板 |
| message_method | string | 是 | 处理方法名称 |
| auto_save_category_id | int\|null | 否 | 默认 null |
| is_builtin | bool | 否 | 默认 false |
| summary_model | string | 否 | 默认 GPT-4.1 |

响应：创建后的完整分类对象，或 400（创建失败）。

### 9.5 更新分类

```
PUT /v1/plan/categories/{category_id}
```

请求体字段均可选。特殊约定：若需将 `auto_save_category_id` 置为 NULL，传 `-1`。

响应：更新后完整对象，或 400 / 404。

### 9.6 删除分类（级联）

```
DELETE /v1/plan/categories/{category_id}
```

依次删除：`document_references` → `execution_logs` → `document_tags` → `plan_documents` → `plan_categories`。

**响应示例：**

```json
{
  "message": "Category and related documents deleted successfully",
  "deleted": {
    "document_references": 5,
    "execution_logs": 12,
    "document_tags": 9,
    "plan_documents": 3
  }
}
```

---

## 十、计划文档管理

> 文档采用只增不改的版本策略：每次写入均生成新版本，旧版本保留。

### 10.1 文档对象字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| project_id | int | 所属项目 |
| category_id | int | 所属分类 |
| filename | string | 文件名（同一分类下唯一标识文档的逻辑名） |
| content | string | 文档内容 |
| version | int | 版本号，自动递增 |
| source | string | 来源：user / server / chat |
| related_log_id | int\|null | 关联执行日志 ID |
| created_time | string | ISO 8601 |

### 10.2 新增文档版本

```
POST /v1/plan/documents
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| project_id | int | 是 | |
| category_id | int | 是 | |
| filename | string | 是 | |
| content | string | 是 | |
| version | int | 否 | 不传则自动递增 |
| source | string | 否 | user / server / chat |
| related_log_id | int | 否 | 关联日志 ID |

响应：新建的文档记录（含 version 与 created_time）。

### 10.3 文档历史版本

```
GET /v1/plan/documents/history?project_id={int}&category_id={int}&filename={string}
```

`category_id` 和 `filename` 均可选，不传表示全项目范围。响应：按 version DESC 排序的列表。

示例（项目 3，分类 5 下所有文档）：

```
GET /v1/plan/documents/history?project_id=3&category_id=5
```

### 10.4 文档最新版本列表（含搜索分页）

```
GET /v1/plan/documents/latest
```

返回每个 filename 的最新版本记录，支持模糊搜索、分页与排序。前端传空字符串参数时后端按默认值处理，不返回 422。

**查询参数：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|:----:|------|------|
| project_id | int | 是 | — | 支持字符串数字（如 "41"） |
| category_id | int | 否 | — | 允许空值，空则视为未提供 |
| query | string | 否 | — | filename 模糊匹配（LIKE %query%），空则不过滤 |
| sort_by | string | 否 | created_time | filename / created_time / version |
| order | string | 否 | desc | asc / desc |
| page | int | 否 | 1 | >=1；允许空，按 1 处理 |
| page_size | int | 否 | 20 | 1~200；允许空，按 20 处理 |

**响应（200）：**

```json
{
  "total": 35,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 123, "project_id": 1, "category_id": 5,
      "filename": "API设计规范.md", "version": 7,
      "content": "...", "source": "user",
      "created_time": "2025-01-08T10:00:00"
    }
  ]
}
```

**调用示例：**

```
GET /v1/plan/documents/latest?project_id=41
GET /v1/plan/documents/latest?project_id=41&category_id=5&query=计划&page=1&page_size=20
GET /v1/plan/documents/latest?project_id=41&category_id=&query=&page=&page_size=
（宽容处理，等价于仅传 project_id）
```

### 10.5 合并多文档

```
POST /v1/plan/documents/merge
```

根据传入的文档 ID 列表，读取各文档的 filename、version 与 content，按顺序拼装为统一文本。

请求体：`{ "document_ids": [101, 102, 103] }`

**响应（200）：**

```json
{
  "count": 3,
  "merged": "--- 需求计划- 版本[7] 开始 ---\n内容A\n--- 需求计划- 版本[7] 结束 ---\n\n..."
}
```

| 错误码 | 说明 |
|--------|------|
| 400 | document_ids 为空 |
| 404 | 文档不存在 |
| 500 | 内部错误 |

> 重复 ID 去重，仅保留首次出现顺序。filename 为空时回退为 `document_{id}`。

### 10.6 文档详情

```
GET /v1/plan/documents/{document_id}
```

响应：文档对象或 404。

### 10.7 编辑文档（生成新版本）

```
PUT /v1/plan/documents/{document_id}
```

更新时创建新版本，不覆盖原版本。所有字段均可选：`filename`、`content`、`source`。

---

## 十一、文档迁移

### 11.1 迁移全历史

```
POST /v1/plan/documents/migrate/all-history
```

将 `source_category_id` 下某 filename 的所有历史版本，按原顺序复制到 `target_category_id`，目标版本号在目标分类已有版本基础上延续。源数据不删除。

**请求体：**

```json
{
  "project_id": 1,
  "source_category_id": 5,
  "target_category_id": 6,
  "filename": "API设计规范.md"
}
```

**响应（200）：**

```json
{
  "message": "Migration completed",
  "migrated_count": 7,
  "target_category_id": 6,
  "filename": "API设计规范.md",
  "start_version": 1,
  "end_version": 7
}
```

### 11.2 从当前版本起迁移

```
POST /v1/plan/documents/migrate/from-current
```

读取 `document_id` 对应记录，复制内容到目标分类，作为新文件名的最新版本。源数据不变。

**请求体：**

```json
{
  "document_id": 321,
  "target_category_id": 6,
  "new_filename": "API规范.md",
  "source": "user"
}
```

`new_filename` 和 `source` 均可选；不填 `new_filename` 则沿用原 filename。

响应：新创建版本的完整文档记录。

---

## 十二、知识库文档引用

> 项目级引用对该项目下所有会话生效；会话级引用仅对特定会话生效，且不能与项目级引用的文档重复。知识库文档即 `category_id=5` 的 plan_documents 记录。

### 12.1 查询会话引用（含项目级+会话级）

```
GET /v1/chat/conversations/{conversation_id}/referenced-documents
```

返回该会话引用的所有文档，分 `project_references` 与 `conversation_references` 两个数组。

**响应示例：**

```json
{
  "conversation_id": "12345",
  "project_references": [
    {
      "id": 1, "project_id": 1, "conversation_id": null,
      "document_id": 100, "reference_type": "project",
      "document_filename": "API设计规范.md",
      "document_content": "...", "document_version": 1,
      "document_created_time": "2024-01-01T10:00:00"
    }
  ],
  "conversation_references": [...]
}
```

### 12.2 项目级引用管理

**查询项目级引用**

```
GET /v1/projects/{project_id}/document-references
```

**设置项目级引用（完全替换）**

```
POST /v1/projects/{project_id}/document-references
```

请求体：`{ "document_ids": [100, 101, 102] }`

```json
{
  "message": "Project document references updated successfully",
  "added_count": 2,
  "removed_count": 1,
  "current_references": [100, 101, 102]
}
```

**清空项目级引用**

```
DELETE /v1/projects/{project_id}/document-references
```

### 12.3 会话级引用管理

**查询会话级引用**

```
GET /v1/chat/conversations/{conversation_id}/document-references
```

**设置会话级引用（完全替换）**

```
POST /v1/chat/conversations/{conversation_id}/document-references
```

请求体：`{ "document_ids": [103, 104] }`

> **限制：** 只能引用其所属项目的文档，且不能引用项目级已引用的文档。违反时返回：
> `{ "detail": "Documents already referenced at project level: [100, 101]" }`

**清空会话级引用**

```
DELETE /v1/chat/conversations/{conversation_id}/document-references
```

---

## 十三、写入源码文件

```
POST /v1/write-source-code
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|:----:|------|------|
| root_dir | string | 是 | — | 源码写入的根目录（绝对路径，需有写权限） |
| files_content | string | 是 | — | 任务定义文件内容（符合规范的结构化文本） |
| log_level | string | 否 | INFO | 日志级别 |
| backup_enabled | bool | 否 | true | 是否启用备份 |

**请求示例：**

```json
{
  "root_dir": "/absolute/path/to/project",
  "files_content": "Step [1/1] - 创建文件\nAction: Create file\nFile Path: src/main.py\n```python\nprint('hello world')\n```",
  "log_level": "INFO",
  "backup_enabled": true
}
```

**响应（流式 SSE）：** Content-Type: `text/event-stream`，每步返回一个 JSON 事件。

`type` 取值：

| type | 说明 |
|------|------|
| info | 一般信息 |
| progress | 进度信息 |
| success | 步骤执行成功 |
| warning | 警告 |
| error | 错误 |
| summary | 最终汇总 |

**普通步骤事件示例（type ≠ summary）：**

```json
{
  "message": "任务执行成功",
  "type": "success",
  "timestamp": "2025-08-18T14:30:25",
  "data": {
    "step_index": 1,
    "action": "create_file",
    "file_path": "src/main.py",
    "backup_path": "backup/src/main.py.bak"
  }
}
```

**汇总事件示例（type=summary）：**

```json
{
  "message": "执行完成",
  "type": "summary",
  "timestamp": "2025-08-18T14:30:30",
  "data": {
    "total_tasks": 5,
    "successful_tasks": 4,
    "failed_tasks": 1,
    "invalid_tasks": 0,
    "execution_time": "2.34s",
    "log_file": "log/execution_20250818_143025.log"
  }
}
```

---

## 十四、实现细节与行为说明

| 条目 | 说明 |
|------|------|
| LLM 后端 | poe 或 openai，由环境变量 `LLM_BACKEND` 控制，详见 config.py 与 llm_router.py |
| SSE 过滤 | 以 `"Thinking..."` 开头的内容分片会被丢弃，不出现在响应输出与落库记录中 |
| 会话活跃度 | 任意消息的插入/更新均会刷新 `conversations.updated_at`，用于最近活动排序 |
| 训练日志 | 非流与流式完整响应记录到 `train_data/YYYY-MM-DD.jsonl`（见 logger.py） |
| 数据库 | 需要 MySQL，连接参数见 db.py |
| 代码模块 | 分类路由：`routes/plan/categories.py`；文档路由：`routes/plan/documents.py`；模型：`routes/plan/models.py` |
| 附件存储 | 上传文件保存至 `ATTACHMENTS_DIR`（默认 `attachments`）；可通过 `ATTACHMENT_BASE_URL` 配置公开访问前缀 |

---

*如有版本冲突，以实际后端代码为准。*
