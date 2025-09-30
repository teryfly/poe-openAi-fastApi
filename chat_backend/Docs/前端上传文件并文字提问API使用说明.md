# 前端上传文件并同时文字提问 API 使用说明

本说明文档面向前端开发者，介绍如何通过同一端点实现“上传文件（图片/PDF 等）+ 文字提问”，并获取 LLM 的回答（支持非流式与流式 SSE）。

后端已实现特性：
- 单一端点：POST /v1/chat/completions
- 支持 Content-Type:
  - application/json（原 OpenAI 兼容）
  - multipart/form-data（上传文件 + 文字）
- 附件保存并生成可访问 URL：
  - 默认本地静态资源: GET /files/{filename}
  - 若配置 ATTACHMENT_BASE_URL，则使用外部 URL 前缀
- 自动将附件 URL 注入到最后一条 user 消息的文本中：
  - 图片：额外注入 [IMAGE_URL] http://... 行
  - 所有附件：注入 [ATTACHMENT] name=... type=... size=...KB url=http://... 行
- 支持流式（SSE）与非流式两种响应

鉴权：
- Header: Authorization: Bearer sk-test-xxxxx（或 poe-sk-xxxxx）

注意：如需多文件上传，在 form-data 中添加多个文件字段（任意字段名均可识别为文件项）。

---

## 一、请求参数（multipart/form-data）

- model: string 必填。示例：GPT-5-Chat、GPT-4.1、ChatGPT-4o-Latest 等
- messages: string 可选。OpenAI chat messages 的 JSON 字符串（数组形式）。若提供将作为基础对话上下文
- text: string 可选。当未提供 messages 时，用作 user 问题文本
- stream: "true" | "false" 可选。是否以 SSE 流式返回，默认 false
- 文件：任意字段名的文件项都会识别为附件。例如 file1、image、pdf 等

至少提供 messages 或 text 或文件 三者之一，否则返回 400。

---

## 二、请求注入规则

后端会将上传文件保存并生成 URL，然后将以下文本追加到最后一个 role=user 的消息内容里：
- 若为图片（content-type 以 image/ 开头）：
  - 先追加一行 [IMAGE_URL] http://host/files/xxx.jpg
- 接着追加一行 [ATTACHMENT] name=原始文件名 type=MIME size=大小(KB) url=公开地址

若 messages 中没有用户消息，将自动创建一条 user 消息，仅包含上述附件标记。

---

## 三、示例

### 1) 非流式：文字 + 图片

curl 示例
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-test-abc123" \
  -F "model=GPT-5-Chat" \
  -F "text=请描述这张图片的内容，并给出三条要点" \
  -F "stream=false" \
  -F "file1=@/path/to/image.jpg"
```

返回（与 OpenAI 兼容）
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

### 2) 流式 SSE：messages + 多文件

curl 示例
```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-test-abc123" \
  -F 'model=ChatGPT-4o-Latest' \
  -F 'stream=true' \
  -F 'messages=[
        {"role":"system","content":"你是一个专业的多模态助手。"},
        {"role":"user","content":"请分析这些附件并回答问题"}
      ]' \
  -F "img=@/path/to/picture.png" \
  -F "pdf=@/path/to/report.pdf"
```

SSE 响应：
- 多个 data: 行，以换行分隔
- 最后以 data: [DONE] 结束
```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"ChatGPT-4o-Latest","choices":[{"index":0,"delta":{"content":"片段1"}}]}
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"ChatGPT-4o-Latest","choices":[{"index":0,"delta":{"content":"片段2"}}]}
...
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"ChatGPT-4o-Latest","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

前端浏览器端使用 EventSource 示例（原生）
```javascript
const formData = new FormData();
formData.append("model", "ChatGPT-4o-Latest");
formData.append("stream", "true");
formData.append("text", "请综合这些附件，总结要点");
formData.append("file1", fileInput.files[0]); // <input type="file" id="fileInput" />

const resp = await fetch("/v1/chat/completions", {
  method: "POST",
  headers: { Authorization: "Bearer sk-test-abc123" },
  body: formData
});

// 使用 ReadableStream 读取 SSE
const reader = resp.body.getReader();
const decoder = new TextDecoder("utf-8");
let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const parts = buffer.split("\n\n");
  buffer = parts.pop() || "";
  for (const part of parts) {
    if (!part.startsWith("data:")) continue;
    const data = part.slice(5).trim();
    if (data === "[DONE]") {
      console.log("Stream done");
      break;
    }
    try {
      const chunk = JSON.parse(data);
      const delta = chunk?.choices?.[0]?.delta?.content ?? "";
      if (delta) {
        // 逐片渲染
        renderDelta(delta);
      }
    } catch (e) {
      console.warn("Non-JSON data:", data);
    }
  }
}
```

前端基于 EventSource 的另一种方式（注意 EventSource 不支持自定义 method/headers，不适用于带鉴权与 form-data 的场景，建议使用 fetch + ReadableStream，如上所示。）

---

## 四、前端（非流式）常用代码示例（fetch）

```javascript
async function askWithFiles({ model, text, files, token }) {
  const formData = new FormData();
  formData.append("model", model);
  formData.append("stream", "false");
  if (text) formData.append("text", text);
  (files || []).forEach((f, idx) => formData.append(`file${idx+1}`, f));

  const resp = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: formData
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}
```

---

## 五、messages 字段（可选）示例

当需要自定义对话上下文时，可以通过 messages（JSON 字符串）传入：
```json
[
  {"role":"system","content":"你是一个有帮助的助手"},
  {"role":"user","content":"结合附件内容，回答我的问题"}
]
```

在 multipart/form-data 中的使用（Postman/前端）：
- Key: messages
- Type: Text
- Value: 上述 JSON 字符串

同时可添加文件字段，后端会自动把附件 URL 注入到最后一条 user 消息。

---

## 六、错误与限制

- 401 Invalid API key format：Authorization 头无效；示例：Bearer sk-test-xxxxx 或 poe-sk-xxxxx
- 400 Missing 'model' field：multipart 未提供 model
- 400 Either 'messages' or 'text' or files must be provided：三者缺失
- 400 Invalid JSON in 'messages'：messages 字段不是合法 JSON 数组
- 413 File too large：超出单文件大小限制（默认 20MB，可通过环境变量 ATTACHMENT_MAX_SIZE_MB 调整）
- 415 Unsupported content type：文件类型不在白名单（默认支持 image/png,image/jpeg,image/webp,application/pdf）
- 415 Unsupported Content-Type：请求头 Content-Type 不受支持
- 500 Save file failed：保存附件失败
- 500 internal_error：服务器内部错误

---

## 七、配置项（后端）

在环境变量或 config.py 中调整：
- ATTACHMENTS_DIR：附件保存目录（默认 attachments）
- ATTACHMENT_MAX_SIZE_MB：单文件最大 MB（默认 20）
- ATTACHMENT_ALLOWED_TYPES：允许的 MIME 类型，逗号分隔
- ATTACHMENT_BASE_URL：若设置，则附件 URL 使用该前缀；否则默认 /files/{filename} 由后端静态路由提供

---

## 八、调试建议

- 本地开发可使用 Postman 选择 Body = form-data，添加 model、text、stream、file1 等
- 观察返回内容中是否包含 [IMAGE_URL] 和 [ATTACHMENT] 标记
- 若前端直连后端，请确保同源或 CORS 允许；已默认允许 http://localhost:5173 与 http://127.0.0.1:5173