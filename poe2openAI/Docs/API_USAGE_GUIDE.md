# OpenAI-Compatible API Proxy to Poe - 使用说明

本系统提供与 OpenAI Chat Completions 兼容的接口，同时支持在同一端点通过 multipart/form-data 上传附件（图片、PDF 等）并携带文字提问，自动将附件转为可访问的 URL 注入消息中，便于具备视觉能力的 Poe 模型解析。

版本：v2.2.x

- 主要端点
  - POST /v1/chat/completions
  - GET  /v1/models
  - GET  /health
  - GET  /files/{filename}
- 认证方式
  - Header: Authorization: Bearer sk-xxxxx

注意：所有示例中的 HOST 使用 http://localhost:8000，请根据实际部署修改。

---

## 1. 认证

在所有需要认证的接口中添加 Header：

- Authorization: Bearer sk-your-key

若 key 不以 "sk-" 开头，将返回 401 Invalid API key format。

---

## 2. 模型列表

- 方法：GET /v1/models
- 认证：需要
- 请求参数：无
- 响应示例：
```json
{
  "object": "list",
  "data": [
    {
      "id": "GPT-5-Chat",
      "object": "model",
      "created": 171536813,
      "owned_by": "openai/38/38/241"
    }
  ]
}
```

模型名称直接为 Poe 的 Bot 名称，例如：GPT-5-Chat、GPT-4.1、Claude-3.7-Sonnet 等。

---

## 3. 健康检查

- 方法：GET /health
- 认证：不需要
- 响应示例：
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00.000000",
  "poe_client": "initialized",
  "active_generators": 0
}
```

---

## 4. 文件访问

- 方法：GET /files/{filename}
- 认证：不需要
- 说明：当通过 multipart 上传文件时，系统会将文件保存在配置的 ATTACHMENTS_DIR 目录，并通过该端点提供公共访问 URL，用于在对话内容中注入图像链接。

---

## 5. 聊天完成接口（Chat Completions）

端点：POST /v1/chat/completions

支持两种请求内容类型：
- application/json（保持原有 OpenAI 兼容）
- multipart/form-data（支持文件上传 + 文本提问）

注意：两种类型共享同一端点，便于升级平滑迁移。

### 5.1 application/json（原有兼容）

- Header：Content-Type: application/json
- Body 字段（与 OpenAI API 对齐的子集）：
  - model: string（Poe 的模型名）
  - messages: ChatMessage[]
  - stream: boolean（默认 false）
  - 其他字段会被忽略或暂不使用（如 tools、functions 等）

- ChatMessage:
  - role: "system" | "user" | "assistant" | "tool" | "function"
  - content: string 或 OpenAI 内容数组（数组会在服务端被扁平化为文本）
  - 可选字段：name、function_call、tool_calls、tool_call_id

- 示例（非流式）：
```json
{
  "model": "GPT-5-Chat",
  "messages": [
    {"role": "system", "content": "你是一个有帮助的助手。"},
    {"role": "user", "content": "你好，今天天气如何？"}
  ],
  "stream": false
}
```

- 示例（流式）：
```json
{
  "model": "GPT-5-Chat",
  "messages": [
    {"role": "user", "content": "用两句话概括相对论"}
  ],
  "stream": true
}
```

- 流式响应格式（SSE）：
  - 逐条返回：`data: {chunk}\n\n`
  - 完成标记：`data: [DONE]\n\n`

- curl 流式示例：
```bash
curl -N -H "Authorization: Bearer sk-your-key" \
     -H "Content-Type: application/json" \
     -d '{"model":"GPT-5-Chat","messages":[{"role":"user","content":"用两句话概括相对论"}],"stream":true}' \
     http://localhost:8000/v1/chat/completions
```

### 5.2 multipart/form-data（上传文件 + 文字）

- Header：Content-Type: multipart/form-data
- 字段约定：
  - model: string（Poe 模型名）必填
  - messages: string（JSON 字符串，OpenAI chat 格式）可选
  - text: string（当未提供 messages 时，用作一条 user 消息文本）可选
  - stream: "true" | "false" 可选，默认 false
  - 文件：任意字段名的文件项都会被识别为附件（如 file1、file2 等）

- 行为：
  - 系统保存上传文件并生成可访问 URL（如 http://host/files/{filename}）
  - 将附件注入到最后一条 role=user 的消息：
    - 图片：追加
      - [IMAGE_URL] http://host/files/xxx.jpg
      - 以及可读的 [ATTACHMENT] 行
    - 其他类型：以 [ATTACHMENT] 行的形式注入
  - 若 messages 的最后一个 user 消息 content 是 OpenAI 内容数组，图片将以 {"type":"image_url","image_url":{"url":"..."}} 的结构追加；并且同时追加一条 {"type":"text","text":"[ATTACHMENT] ..."} 便于模型理解
  - 最终发送给 Poe 的内容为纯文本（包含 URL 标记），以确保绝大多数 Poe bots 能够消费

- Postman 操作步骤：
  1) Method: POST，URL: http://localhost:8000/v1/chat/completions
  2) Headers: Authorization: Bearer sk-your-key
  3) Body 选择 form-data，添加：
     - model: GPT-5-Chat
     - text: 请描述这张图片的内容
     - stream: true
     - file1: 选择一张图片
     - （可再添加 file2、pdf 等）

- curl 流式示例：
```bash
curl -N -H "Authorization: Bearer sk-your-key" \
     -F "model=GPT-5-Chat" \
     -F "text=请描述这张图片的内容" \
     -F "stream=true" \
     -F "file1=@/path/to/image.jpg" \
     http://localhost:8000/v1/chat/completions
```

- 自定义 messages（含 content 数组）+ 文件 示例（Postman 中 messages 字段类型为 Text，内容为 JSON）：
```json
[
  {"role":"system","content":"你是一个专业的多模态助手。"},
  {"role":"user","content":[{"type":"text","text":"请分析这张图片"}]}
]
```

### 5.3 响应格式

- 非流式响应（与 OpenAI 兼容）：
```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": 1736400000,
  "model": "GPT-5-Chat",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "回答内容"},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 20,
    "total_tokens": 32
  }
}
```

- 流式响应（SSE）：
  - 多个 data: 行，每个包含 ChatCompletionStreamResponse（object: "chat.completion.chunk"）
  - 最后以 `data: [DONE]` 结束

---

## 6. 附件与视觉输入

- 受支持的类型由配置 ATTACHMENT_ALLOWED_TYPES 控制，默认：
  - image/png,image/jpeg,image/webp,application/pdf
- 单文件大小限制由 ATTACHMENT_MAX_SIZE_MB 控制（默认 20 MB）
- 文件保存目录 ATTACHMENTS_DIR（默认 attachments）
- 若设置 ATTACHMENT_BASE_URL，则生成 URL 使用该前缀；否则使用内置 /files/{filename}

注：对 Poe 的视觉理解取决于所选模型是否具备视觉能力。我们的实现保证把图片 URL 明确注入文本，使具备视觉能力的模型可获取图片链接。

---

## 7. 日志

- 按日期写入 JSONL：train_data/YYYY-MM-DD.jsonl
- 记录内容包含：
  - 请求（包括 multipart 模式下的附件元信息：文件名、类型、大小、URL）
  - 响应（流式则记录完整合并文本与长度）

---

## 8. 错误码与常见错误

- 400 Invalid JSON body：application/json 解析失败
- 400 Missing 'model' field：multipart 未提供 model
- 400 Either 'messages' or 'text' or files must be provided：multipart 同时缺少 messages、text 和文件
- 400 Invalid JSON in 'messages'：multipart 的 messages 字段非合法 JSON
- 401 Invalid API key format：认证头不合法
- 413 File too large：超出最大文件大小
- 415 Unsupported content type：文件类型不在白名单
- 500 Poe client not initialized：Poe 客户端不可用
- 500 internal_error：代理内部错误

---

## 9. 配置项（config.py）

- HOST/PORT：服务监听地址与端口
- LOG_DIR：日志目录（默认 train_data）
- TIMEOUT_KEEP_ALIVE/TIMEOUT_GRACEFUL_SHUTDOWN/TIMEOUT_HTTP：超时相关
- ATTACHMENTS_DIR：附件目录（默认 attachments）
- ATTACHMENT_MAX_SIZE_MB：单文件最大 MB（默认 20）
- ATTACHMENT_ALLOWED_TYPES：允许的 MIME 类型列表（以逗号分隔）
- ATTACHMENT_BASE_URL：若前置有文件 CDN/网关，可设置成 http(s)://cdn.example.com/path

---

## 10. 版本与特性摘要

- 与 OpenAI Chat Completions 兼容
- 同一端点支持 application/json 与 multipart/form-data
- 视觉输入：自动将图片转为公开 URL 注入消息文本
- 流式 SSE 响应
- 完整请求/响应日志
- 无超时配置、优雅关闭、稳定的异步流包装

