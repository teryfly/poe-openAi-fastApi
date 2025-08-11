
# chat_backend API 文档

版本: 2.3.0  
Base URL: http://{HOST}:{PORT}（默认 8000）  
认证方式: HTTP Bearer（Authorization: Bearer ），需以 sk-test 或 poe-sk 开头

说明:
- JSON 编码 UTF-8；时间戳为 ISO8601 字符串
- SSE 流响应 Content-Type: text/event-stream
- 错误格式: {"detail": "错误信息"}

## API 索引

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| GET | / | 否 | 根信息 |
| GET | /health | 否 | 健康检查 |
| GET | /v1/models | 否 | 模型列表 |
| POST | /v1/chat/completions | 是 | OpenAI 兼容聊天（支持 SSE） |
| POST | /v1/chat/conversations | 否 | 创建会话 |
| GET | /v1/chat/conversations | 否 | 会话列表（支持过滤） |
| GET | /v1/chat/conversations/grouped | 否 | 按项目分组的会话 |
| GET | /v1/chat/conversations/{conversation_id} | 否 | 会话详情 |
| PUT | /v1/chat/conversations/{conversation_id} | 否 | 更新会话 |
| DELETE | /v1/chat/conversations/{conversation_id} | 否 | 删除会话 |
| GET | /v1/chat/conversations/{conversation_id}/messages | 否 | 会话消息列表 |
| POST | /v1/chat/conversations/{conversation_id}/messages | 是 | 追加消息并获取回复（支持 SSE） |
| POST | /v1/chat/messages/delete | 否 | 批量删除消息 |
| POST | /v1/chat/stop-stream | 否 | 停止正在进行的流式会话 |
| GET | /v1/projects | 否 | 项目列表 |
| GET | /v1/projects/{id} | 否 | 项目详情 |
| POST | /v1/projects | 否 | 新建项目 |
| PUT | /v1/projects/{id} | 否 | 更新项目 |
| DELETE | /v1/projects/{id} | 否 | 删除项目 |
| GET | /v1/projects/{id}/complete-source-code | 否 | 聚合工程源码文本 |
| GET | /v1/plan/categories | 否 | 计划分类列表 |
| POST | /v1/plan/documents | 否 | 新增计划文档（版本自增） |
| GET | /v1/plan/documents/history | 否 | 文档历史版本 |

鉴权说明:
- 需要访问 LLM 的接口必须带 Authorization 头：/v1/chat/completions 与 POST /v1/chat/conversations/{id}/messages
- 其他接口当前未强制鉴权

---

## 通用对象

- 项目 Project 字段
  - id, name, dev_environment, grpc_server_address
  - llm_model, llm_url, git_work_dir, ai_work_dir
  - created_time, updated_time

- 会话 Conversation 字段
  - id, system_prompt, status, created_at, updated_at, project_id, name, model, assistance_role

- 消息 Message 字段
  - id, conversation_id, role, content, created_at, updated_at

---

## Misc

1) GET /
- 响应: 服务信息、版本、当前 LLM 后端与常用端点

2) GET /health
- 响应: {"status":"healthy","timestamp":"...","llm_backend":"..."}

3) GET /v1/models
- 响应: { "object":"list", "data": [ { "id":"...", "object":"model", "created": 171..., "owned_by":"..." }, ... ] }

---

## OpenAI 兼容聊天

POST /v1/chat/completions 需要鉴权  
请求体(关键字段):
- model: string
- messages: [{role: "system"|"user"|"assistant"|"tool"|"function", content: string}]
- stream: bool（默认 false）
- 可选: functions/tools 等原生 OpenAI 字段（透传）

关联会话的两种方式（二选一）:
- 在最后一条消息的 name 填写 "cid-"
- 非标准：若消息对象带有 conversation_id 字段（当前模型未定义，不建议使用）

非流式响应:
- 标准 OpenAI JSON：choices[0].message.content 等
- usage 为基于空格分词的简易统计

SSE 流式响应:
- 逐帧发送 {"id","object":"chat.completion.chunk","created","model","choices":[{"delta":{"content":"..."},"index":0}]}
- 结束帧 finish_reason="stop"，然后 data: [DONE]
- 过滤策略：以 "Thinking..." 开头的分片会被忽略，不会出现在输出和落库

示例请求:
```json
{
  "model": "GPT-4.1",
  "messages": [
    {"role":"system","content":"You are helpful."},
    {"role":"user","content":"Hello"},
    {"role":"user","content":"继续", "name": "cid-"}
  ],
  "stream": true
}
```

---

## 会话管理

1) 创建会话  
POST /v1/chat/conversations
- 请求体:
  - system_prompt?: string
  - project_id: int (默认 0)
  - name?: string
  - model?: string
  - assistance_role?: string
  - status?: int (0 正常, 1 存档等；默认 0)
- 响应: {"conversation_id": "uuid"}

2) 获取会话列表  
GET /v1/chat/conversations?project_id={int}&status={int}
- 响应: Conversation[]（含 status/updated_at 等）

3) 按项目分组  
GET /v1/chat/conversations/grouped
- 响应: { "": Conversation[], ... }

4) 会话详情  
GET /v1/chat/conversations/{conversation_id}
- 404: 未找到

5) 更新会话  
PUT /v1/chat/conversations/{conversation_id}
- 请求体(任意字段可选): {project_id?, name?, model?, assistance_role?, status?}
- 响应: {"message":"Conversation updated"} 或 404

6) 删除会话  
DELETE /v1/chat/conversations/{conversation_id}
- 响应: {"message":"Conversation deleted"} 或 404

---

## 消息管理

1) 获取消息列表  
GET /v1/chat/conversations/{conversation_id}/messages
- 响应: {"conversation_id":"...","messages":[Message,...]} 或 404

2) 追加消息并获取回复（需鉴权）  
POST /v1/chat/conversations/{conversation_id}/messages
- 请求体: { role:"user"|"assistant"|..., content:string, model:string="ChatGPT-4o-Latest", stream:bool=false }
- 非流式响应:
  - {"conversation_id":"...","reply":"...","user_message_id":int|null,"assistant_message_id":int}
- SSE 流式:
  - 首帧: {"user_message_id":int|null,"assistant_message_id":int,"conversation_id":"...","session_id":"..."}
  - 多帧: {"content":"partial text"}
  - 完成: {"content":"","finish_reason":"stop"} + [DONE]
- 忽略用户策略:
  - 若 role=user 且 content 完全匹配 Config.ignoredUserMessages，则不会入库该 user 消息，但仍可带入上下文

3) 批量删除消息  
POST /v1/chat/messages/delete
- 请求体: {"message_ids":[int,...]}
- 响应: {"message":"{n} messages deleted"}

4) 停止流式会话  
POST /v1/chat/stop-stream
- 请求体: {"session_id":"..."}
- 响应: {"message":"Stream stopped","session_id":"..."}

---

## 项目管理

表结构（简要）：  
id, name(唯一), dev_environment, grpc_server_address, llm_model, llm_url, git_work_dir, ai_work_dir, created_time, updated_time

1) 项目列表  
GET /v1/projects
- 响应: Project[]

2) 项目详情  
GET /v1/projects/{id}
- 响应: Project 或 404

3) 新建项目  
POST /v1/projects
- 请求体(全量字段):
  - name: string
  - dev_environment: string
  - grpc_server_address: string
  - llm_model?: string = "GPT-4.1"
  - llm_url?: string = "http://43.132.224.225:8000/v1/chat/completions"
  - git_work_dir?: string = "/git_workspace"
  - ai_work_dir?: string = "/aiWorkDir"
- 响应: 新建 Project（含 created_time/updated_time）

4) 更新项目（部分字段）  
PUT /v1/projects/{id}
- 请求体(任意字段可选): 同上字段可选择性提交
- 响应: 更新后的 Project 或 404

5) 删除项目  
DELETE /v1/projects/{id}
- 响应: {"message":"Project deleted successfully"} 或 404

6) 获取完整源码文本  
GET /v1/projects/{id}/complete-source-code
- 响应: {"completeSourceCode":""}
- 说明: 依赖第三方库 code_project_reader 与数据库中的 ai_work_dir 路径

示例创建请求:
```json
{
  "name":"demo",
  "dev_environment":"python3.11",
  "grpc_server_address":"192.168.120.238:50051",
  "llm_model":"GPT-4.1",
  "llm_url":"http://43.132.224.225:8000/v1/chat/completions",
  "git_work_dir":"/git_workspace",
  "ai_work_dir":"/aiWorkDir"
}
```

---

## 计划管理

1) 分类列表  
GET /v1/plan/categories
- 响应: [{id,name,prompt_template,message_method,auto_save_category_id,is_builtin,created_time}, ...]

2) 新增文档（永远新增版本）  
POST /v1/plan/documents
- 请求体: {project_id:int, category_id:int, filename:string, content:string, version?:int, source?:"user"|"server"|"chat", related_log_id?:int}
- 响应: 新记录（含 version 与 created_time）

3) 文档历史  
GET /v1/plan/documents/history?project_id={int}&category_id={int}&filename={string}
- 响应: 按 version DESC 的列表

---

## 实现细节与行为说明

- LLM 后端: poe 或 openai，通过环境变量 LLM_BACKEND 控制，详见 config.py 与 llm_router.py
- SSE 过滤: 所有以 "Thinking..." 开头的内容会被丢弃
- 会话活跃度: 任意插入/更新消息会刷新 conversations.updated_at，用于最近活动排序
- 训练日志: 非流与流式完整响应会记录到 train_data/YYYY-MM-DD.jsonl（见 logger.py）
- 数据库: 需要 MySQL（见 db.py 的连接参数）
```