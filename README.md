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
| 获取项目全量源代码 | `GET /v1/projects/2/complete-source-code` | 入参项目id,出参completeSourceCode |

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


### 1. 获取会话消息（GET）

**接口：**
```
GET /v1/chat/conversations/{conversation_id}/messages
```

**请求示例：**
```http
GET /v1/chat/conversations/2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41/messages
Authorization: Bearer sk-test-xxxx
```

**返回示例：**
```json
{
  "conversation_id": "2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41",
  "messages": [
    {
      "id": 101,
      "role": "system",
      "content": "你是AI助手，帮我写代码。"
    },
    {
      "id": 102,
      "role": "user",
      "content": "用Python写一个冒泡排序"
    },
    {
      "id": 103,
      "role": "assistant",
      "content": "这是Python实现的冒泡排序：\n```python\n def bubble_sort(arr): ..."
    }
  ]
}
```

---

### 2. 添加新消息并获得回复（POST）

**接口：**
```
POST /v1/chat/conversations/{conversation_id}/messages
```

**请求示例：**
```http
POST /v1/chat/conversations/2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41/messages
Authorization: Bearer sk-test-xxxx
Content-Type: application/json

{
  "role": "user",
  "content": "请用Java写冒泡排序",
  "model": "ChatGPT-4o-Latest",
  "stream": false
}
```

**返回示例：**
```json
{
  "conversation_id": "2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41",
  "reply": "这是Java实现的冒泡排序：\n```java\nvoid bubbleSort(int[] arr) {...}\n```",
  "user_message_id": 104,
  "assistant_message_id": 105
}
```

---

### 3. 添加新消息并获得流式回复（POST，流式响应）

**请求：**
```http
POST /v1/chat/conversations/2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41/messages
Authorization: Bearer sk-test-xxxx
Content-Type: application/json

{
  "role": "user",
  "content": "请用C++写冒泡排序",
  "model": "ChatGPT-4o-Latest",
  "stream": true
}
```

**流式响应示例（text/event-stream）：**
```
data: {"user_message_id":106,"assistant_message_id":107,"conversation_id":"2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41"}

data: {"content":"这是C++实现的冒泡排序：\n"}
data: {"content":"```cpp\n"}
data: {"content":"void bubbleSort(int arr[], int n) {"}
data: {"content":" ..."}
data: {"content":"}\n```"}
data: {"content":"","finish_reason":"stop"}
data: [DONE]
```


### 1. 获取会话消息（GET）

**接口：**
```
GET /v1/chat/conversations/{conversation_id}/messages
```

**请求示例：**
```http
GET /v1/chat/conversations/2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41/messages
Authorization: Bearer sk-test-xxxx
```

**返回示例：**
```json
{
  "conversation_id": "2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41",
  "messages": [
    {
      "id": 101,
      "role": "system",
      "content": "你是AI助手，帮我写代码。"
    },
    {
      "id": 102,
      "role": "user",
      "content": "用Python写一个冒泡排序"
    },
    {
      "id": 103,
      "role": "assistant",
      "content": "这是Python实现的冒泡排序：\n```python\n def bubble_sort(arr): ..."
    }
  ]
}
```

---

### 2. 添加新消息并获得回复（POST）

**接口：**
```
POST /v1/chat/conversations/{conversation_id}/messages
```

**请求示例：**
```http
POST /v1/chat/conversations/2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41/messages
Authorization: Bearer sk-test-xxxx
Content-Type: application/json

{
  "role": "user",
  "content": "请用Java写冒泡排序",
  "model": "ChatGPT-4o-Latest",
  "stream": false
}
```

**返回示例：**
```json
{
  "conversation_id": "2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41",
  "reply": "这是Java实现的冒泡排序：\n```java\nvoid bubbleSort(int[] arr) {...}\n```",
  "user_message_id": 104,
  "assistant_message_id": 105
}
```

---

### 3. 添加新消息并获得流式回复（POST，流式响应）

**请求：**
```http
POST /v1/chat/conversations/2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41/messages
Authorization: Bearer sk-test-xxxx
Content-Type: application/json

{
  "role": "user",
  "content": "请用C++写冒泡排序",
  "model": "ChatGPT-4o-Latest",
  "stream": true
}
```

**流式响应示例（text/event-stream）：**
```
data: {"user_message_id":106,"assistant_message_id":107,"conversation_id":"2a9f9f7a-7a7f-4d5b-bb2b-04e4bb9fce41"}

data: {"content":"这是C++实现的冒泡排序：\n"}
data: {"content":"```cpp\n"}
data: {"content":"void bubbleSort(int arr[], int n) {"}
data: {"content":" ..."}
data: {"content":"}\n```"}
data: {"content":"","finish_reason":"stop"}
data: [DONE]
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
## 获取项目全量源代码 API, 入参项目id,出参completeSourceCode
示例调用方式
请求：

GET /v1/projects/2/complete-source-code
返回：
json
{
  "completeSourceCode": "import os\n\n# main.py\nprint('Hello World')\n..."
}

**注意：** 需要在项目根目录设置 .gitignore 文件 ，用于排除指定的源码文件
