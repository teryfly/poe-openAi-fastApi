# OpenAI-Compatible API Proxy 使用说明

本系统提供与 OpenAI Chat Completions 兼容的接口。

版本：v2.2.x

- 主要端点
  - POST /v1/chat/completions
  - GET  /v1/models
  
    
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

data.id 为可使用的模型名称，例如：GPT-5-Chat、GPT-4.1、Claude-3.7-Sonnet 等。



---

## 3. 聊天完成接口（Chat Completions）

端点：POST /v1/chat/completions

支持两种请求内容类型：
- application/json（保持原有 OpenAI 兼容）
- multipart/form-data（支持文件上传 + 文本提问）

注意：两种类型共享同一端点，便于升级平滑迁移。

### 3.1 application/json

- Header：Content-Type: application/json
- Body 字段（与 OpenAI API 对齐的子集）：
  - model: string（使用模型列表接口查询出的模型名）
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

### 3.2 响应格式

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

