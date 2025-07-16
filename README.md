# poe-openAi-fastApi
proxy for poe using openai style api

完整接口使用示例
- 创建新会话

POST /v1/chat/conversations
Content-Type: application/json

{
  "system_prompt": "You are a helpful assistant."
}
返回：

{ "conversation_id": "xxx-xxx-xxx-xxx" }
- 追加一轮消息并获得回复

POST /v1/chat/conversations/{conversation_id}/messages
Authorization: Bearer poe-sk-xxxx
Content-Type: application/json

{
  "role": "user",
  "content": "你好",
  "model": "Claude-3.5-Sonnet"
}
返回：

{
  "conversation_id": "...",
  "reply": "你好，有什么可以帮您？"
}
- 获取历史

GET /v1/chat/conversations/{conversation_id}/messages
返回：

{
  "conversation_id": "...",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    ...
  ]
}


流式多轮请求示例

POST /v1/chat/conversations/{conversation_id}/messages
Authorization: Bearer poe-sk-xxxx
Content-Type: application/json

{
  "role": "user",
  "content": "你好，帮我写个Python冒泡排序。",
  "model": "ChatGPT-4o-Latest",
  "stream": true
}

### 说明
多轮API（流式/非流式）都自动维护历史，无需客户端拼接。
流式返回为SSE格式，每个 data: 块内为 {"content": ...}，最后 data: [DONE]。
非流式返回和原本一致。
流式时，助手回复会自动在后台追加到会话历史中。


新增和更新的会话相关 API 的 **完整使用示例文档（Postman/curl 格式）**，可直接复制测试。

---

## ✅ 1. 创建会话（支持 `project_id`）

### 请求

```http
POST /v1/chat/conversations
Content-Type: application/json
```

### 示例 JSON Body

```json
{
  "system_prompt": "你是一个项目助手。",
  "project_id": 2
}
```

### curl 示例

```bash
curl -X POST http://localhost:8000/v1/chat/conversations \
  -H "Content-Type: application/json" \
  -d '{"system_prompt": "你是一个项目助手。", "project_id": 2}'
```

### 响应

```json
{
  "conversation_id": "adf2f76c-xxxx-xxxx-xxxx-0dd8c0747fef"
}
```

---

## ✅ 2. 获取所有会话（按项目名分组）

### 请求

```http
GET /v1/chat/conversations/grouped
```

### curl 示例

```bash
curl http://localhost:8000/v1/chat/conversations/grouped
```

### 响应示例

```json
{
  "项目A": [
    {
      "conversation_id": "123...",
      "system_prompt": "你是一个项目助手。",
      "created_at": "2025-07-15T23:00:00",
      "project_id": 2,
      "project_name": "项目A"
    }
  ],
  "其它": [
    {
      "conversation_id": "abc...",
      "system_prompt": null,
      "created_at": "2025-07-14T19:22:00",
      "project_id": 0,
      "project_name": "其它"
    }
  ]
}
```

---

## ✅ 3. 更新会话所属项目

### 请求

```http
PUT /v1/chat/conversations/{conversation_id}
Content-Type: application/json
```

### 示例 JSON Body

```json
{
  "project_id": 1
}
```

### curl 示例

```bash
curl -X PUT http://localhost:8000/v1/chat/conversations/adf2f76c-xxxx-xxxx-xxxx-0dd8c0747fef \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1}'
```

### 响应

```json
{
  "message": "Conversation updated"
}
```

---

## ✅ 4. 删除会话

### 请求

```http
DELETE /v1/chat/conversations/{conversation_id}
```

### curl 示例

```bash
curl -X DELETE http://localhost:8000/v1/chat/conversations/adf2f76c-xxxx-xxxx-xxxx-0dd8c0747fef
```

### 响应

```json
{
  "message": "Conversation deleted"
}
```


