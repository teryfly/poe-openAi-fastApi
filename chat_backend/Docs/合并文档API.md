# 合并文档 API
POST /v1/plan/documents/merge
说明：
- 根据传入的一个或多个文档 ID，读取各文档的标题（filename）、版本（version）与内容（content）
- 按传入顺序拼装为统一文本，文档段之间以空行分隔
- 
请求体（JSON）：
{
  "document_ids": [101, 102, 103]
}
响应（200）：
{
  "count": 3,
  "merged": "--- 需求计划- 版本[7] 开始 ---\n内容A\n--- 需求计划- 版本[7] 结束 ---\n\n--- 开发计划- 版本[2] 开始 ---\n内容B\n--- 开发计划- 版本[2] 结束 ---\n\n--- 测试计划- 版本[1] 开始 ---\n内容C\n--- 测试计划- 版本[1] 结束 ---"
}
错误：
- 400 document_ids cannot be empty
- 404 Documents not found
- 500 内部错误
- 
示例（curl）：
```bash
curl -X POST http://localhost:8000/v1/plan/documents/merge \
  -H "Content-Type: application/json" \
  -d '{"document_ids":[101,102,103]}'
```
备注：

若某个文档的标题为空，将回退为 document_{id}

去重逻辑：当传入重复 ID 时，仅按首次出现的顺序保留一次
