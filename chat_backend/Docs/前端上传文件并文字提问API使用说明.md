
# 聊天对话场景：上传附件 + 文字提问（Poe 标准 messages[].content）

本文档用于前端接入以下能力：

1. 先上传附件，拿到 `filename` 与 `absolute_path`
2. 在会话消息接口中，用 Poe 标准 `messages[].content`（`text / image_url / file`）发送
3. 后端在会话中持久化结构化附件内容，后续对话自动带入附件历史上下文
4. 支持**一次上传多个附件**，也支持**多次上传后合并多个附件+文字提问**

---

## 1）上传附件（支持单文件/多文件）

- 接口：`POST /v1/chat/upload-file`
- Content-Type：`multipart/form-data`
- Header：`Authorization: Bearer sk-test-xxxx`（或 poe-sk-xxxx）

### form-data 字段

- `project_name`：项目名（必填）
- `conversation_name`：会话名（必填）
- `files`：可重复多个文件字段（推荐）
- `file`：单文件字段（兼容旧方式）

### 响应示例

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

---

## 2）会话接口发送结构化内容（推荐）

- 接口：`POST /v1/chat/conversations/{conversation_id}/messages`
- 该接口会把结构化附件内容持久化到数据库，并在后续消息自动带入历史上下文。

### 请求体示例（多文件 + 图片 + 文本）

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

> 后端会把绝对路径自动转为 Poe 兼容的 `data:` 格式后再调用 Poe API。

---

## 3）多次上传后，再一次提问（推荐流程）

### 第一步：第一次上传（比如 2 个文件）

上传后保存返回 `files[]` 到前端状态（如 `uploadedAttachments`）。

### 第二步：第二次上传（再加 1 个文件）

把新返回 `files[]` 继续追加到 `uploadedAttachments`。

### 第三步：发起提问时，把已上传附件全部组装进 content

即一次消息里放入 `text + 多个 file/image_url`。

---

## 4）前端调用示例（多次上传 + 一次提问）

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

  const body = {
    role: "user",
    model: "Claude-Sonnet-4.5",
    stream: false,
    content
  };

  const resp = await fetch(`/v1/chat/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(body)
  });
  if (!resp.ok) throw new Error("ask failed");
  return resp.json();
}
```

---

## 5）/v1/chat/completions + cid-xxx 方式（可选）

当使用 `POST /v1/chat/completions` 时，可在某条消息设置 `name: "cid-{conversation_id}"`。
后端会把该次结构化附件内容与回复持久化到对应会话，后续会话消息自动带入。

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
