# ✨ Poe OpenAI FastAPI Proxy

基于 FastAPI 的后端服务，使用 OpenAI 风格 API 对接 Poe、OpenAI 模型，支持流式与非流式对话、多项目分类、多轮记录、文档计划生成等功能。

---

## 🔗 接口总览

| 功能            | 接口                                                       | 描述            |
| ------------- | -------------------------------------------------------- | ------------- |
| ✅ 创建会话        | `POST /v1/chat/conversations`                            | 支持指定项目、角色、模型  |
| ✅ 追加消息并回复     | `POST /v1/chat/conversations/{conversation_id}/messages` | 支持流式与非流式      |
| ✅ 获取会话历史      | `GET /v1/chat/conversations/{conversation_id}/messages`  | 返回多轮完整消息      |
| ✅ 获取会话列表      | `GET /v1/chat/conversations/grouped`                     | 按项目分组返回       |
| ✅ 更新会话        | `PUT /v1/chat/conversations/{conversation_id}`           | 更新项目、名称、模型、角色 |
| ✅ 删除会话        | `DELETE /v1/chat/conversations/{conversation_id}`        | 单个会话删除        |
| ✅ 删除消息（单条或多条） | `POST /v1/chat/messages/delete`                          | 批量删除消息        |
| ✅ 更新消息内容      | `PUT /v1/chat/messages/{message_id}`                     | 修改指定消息内容      |
| ✅ 获取计划分类      | `GET /v1/plan/categories`                                | 用于生成文档的分类     |
| ✅ 新建计划文档      | `POST /v1/plan/documents`                                | 保存聊天生成的文档     |

---

## 💬 会话使用示例

### 1. 创建新会话

```http
POST /v1/chat/conversations
Content-Type: application/json

{
  "system_prompt": "You are a helpful assistant."
}
```

响应：

```json
{ "conversation_id": "xxx-xxx-xxx-xxx" }
```

---

### 2. 追加一轮消息并获得助手回复（非流式）

```http
POST /v1/chat/conversations/{conversation_id}/messages
Authorization: Bearer poe-sk-xxxx
Content-Type: application/json

{
  "role": "user",
  "content": "你好",
  "model": "Claude-3.5-Sonnet"
}
```

响应：

```json
{
  "conversation_id": "...",
  "reply": "你好，有什么可以帮您？"
}
```

---

### 3. 获取历史消息

```http
GET /v1/chat/conversations/{conversation_id}/messages
```

响应：

```json
{
  "conversation_id": "...",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

---

### 4. 流式请求

```http
POST /v1/chat/conversations/{conversation_id}/messages
Authorization: Bearer poe-sk-xxxx
Content-Type: application/json

{
  "role": "user",
  "content": "你好，帮我写个Python冒泡排序。",
  "model": "ChatGPT-4o-Latest",
  "stream": true
}
```

说明：

* 返回为 SSE 流格式
* 每段 `data: {"content": "..."}`，最后 `data: [DONE]`
* 历史自动记录，无需客户端拼接

---

## 🧠 会话管理 API（增强）

### ✅ 创建带项目的新会话

```http
POST /v1/chat/conversations
Content-Type: application/json

{
  "system_prompt": "你是一个项目助手。",
  "project_id": 2
}
```

---

### ✅ 获取所有会话（按项目分组）

```http
GET /v1/chat/conversations/grouped
```

---

### ✅ 更新会话信息

```http
PUT /v1/chat/conversations/{conversation_id}
Content-Type: application/json

{
  "project_id": 1,
  "name": "我的新会话",
  "model": "Claude-3.5-Sonnet",
  "assistance_role": "产品经理"
}
```

---

### ✅ 删除会话

```http
DELETE /v1/chat/conversations/{conversation_id}
```

---

## 🧹 删除消息 API

统一支持删除一条或多条消息。

```http
POST /v1/chat/messages/delete
Content-Type: application/json

{
  "message_ids": [12345]  // 或多个 [12345, 12346]
}
```

响应：

```json
{ "message": "2 messages deleted" }
```

---

## 🛠️ 更新消息 API

用于更新已有消息内容（如后处理）

```http
PUT /v1/chat/messages/{message_id}
Content-Type: application/json

{
  "content": "更新后的消息内容",
  "created_at": "2025-07-26T12:00:00"  // 可选
}
```

响应：

```json
{ "message": "Message updated" }
```

---

## 📚 计划类 API

### ✅ 获取计划分类列表

```http
GET /v1/plan/categories
```

返回：

```json
[
  {
    "id": 1,
    "name": "需求评审",
    "prompt_template": "...",
    "message_method": "...",
    "is_builtin": true
  }
]
```

---

### ✅ 新建计划文档

```http
POST /v1/plan/documents
Content-Type: application/json

{
  "project_id": 1,
  "category_id": 2,
  "filename": "新方案设计.md",
  "content": "文档内容",
  "version": 1,
  "source": "chat"
}
```

---

## ❌ 错误响应示例

```json
{
  "detail": "Conversation not found"
}
```

---

