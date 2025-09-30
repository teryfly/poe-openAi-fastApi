# 单独上传文件 API（先上传再与消息一起发送）

当需要先上传文档/图片，再与消息一起发送到 /v1/chat/completions 时，可使用本接口。

- 方法：POST /v1/chat/upload-file
- 鉴权：Header Authorization: Bearer sk-test-xxxxx（或 poe-sk-xxxxx）
- Content-Type：multipart/form-data
- 请求字段：
  - file: File 必填，单文件

- 成功响应（200）：
​```json
{
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "size": 123456,
  "url": "/files/2b3c...e7a.pdf",
  "is_image": false,
  "attachment_text_line": "[ATTACHMENT] name=report.pdf type=application/pdf size=120.6KB url=/files/2b3c...e7a.pdf"
}
```

说明：

- url：可公开访问的文件 URL。若配置了 ATTACHMENT_BASE_URL，则为完整外部链接；否则为后端静态路径 /files/{filename}
- is_image：是否图片（content-type 以 image/ 开头）
- attachment_text_line：标准化的注入文本行，前端可直接拼到 user 消息内容末尾；若是图片，建议同时手动追加一行 `[IMAGE_URL] {url}`

示例（curl）：

```bash
curl -X POST http://localhost:8000/v1/chat/upload-file \
  -H "Authorization: Bearer sk-test-abc123" \
  -F "file=@/path/to/report.pdf"
```

前端用法（先传文件，再发送问题）：

```javascript
// 1. 上传文件
const fd = new FormData();
fd.append("file", file); // File 对象
const upResp = await fetch("/v1/chat/upload-file", {
  method: "POST",
  headers: { Authorization: "Bearer sk-test-abc123" },
  body: fd
});
if (!upResp.ok) throw new Error("Upload failed");
const { url, is_image, attachment_text_line } = await upResp.json();

// 2. 组装 user 消息内容
let userContent = "请分析这个文档，并总结关键点。";
const prefix = is_image ? `[IMAGE_URL] ${url}\n` : "";
userContent += `\n\n${prefix}${attachment_text_line}`;

// 3. 非流式调用
const fd2 = new FormData();
fd2.append("model", "ChatGPT-4o-Latest");
fd2.append("text", userContent);
fd2.append("stream", "false");
const resp = await fetch("/v1/chat/completions", {
  method: "POST",
  headers: { Authorization: "Bearer sk-test-abc123" },
  body: fd2
});
const data = await resp.json();
console.log(data);

// 或使用 messages（保持系统消息/上下文）
/*
fd2.append("messages", JSON.stringify([
  {"role":"system","content":"你是一个有帮助的助手"},
  {"role":"user","content": userContent}
]));
*/
```

错误码：

- 401 Invalid API key format
- 413 File too large（默认 20MB）
- 415 Unsupported content type（默认允许 image/png,image/jpeg,image/webp,application/pdf）
- 500 Upload failed

```
