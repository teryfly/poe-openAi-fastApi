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