import asyncio
import time
import uuid
import os
import sys
from datetime import datetime
from typing import Dict, Any
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Security, Request, Path, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
import json
import logging

# 确保导入顺序
try:
    from config import Config
    from models import *
    from poe_client import PoeClient
    from logger import request_logger
    from conversation_manager import conversation_manager
except ImportError as e:
    print(f"Import error: {e}")
    print("Please make sure all required files are in the same directory")
    sys.exit(1)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpenAI Compatible API Proxy to Poe",
    description="A proxy service that provides OpenAI-compatible API forwarding to Poe",
    version="2.1.0"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)

# 安全认证
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    """验证API密钥"""
    if not credentials.credentials.startswith("sk-test"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    return credentials.credentials

# 自定义异常处理器
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误"""
    logger.error(f"Validation error: {exc.errors()}")
    try:
        body = await request.body()
        logger.error(f"Request body: {body.decode()}")
    except Exception as e:
        logger.error(f"Could not read request body: {e}")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": "Invalid request format",
                "type": "invalid_request_error",
                "code": "invalid_request_error",
                "details": exc.errors()
            }
        }
    )

def preserve_all_content(content_data: Any) -> str:
    """保留所有内容信息的转换函数"""
    if isinstance(content_data, str):
        return content_data
    elif isinstance(content_data, list):
        preserved_parts = []
        for item in content_data:
            if isinstance(item, dict):
                if 'type' in item and 'text' in item:
                    preserved_parts.append(item['text'])
                elif 'tool' in item:
                    tool_info = json.dumps(item, ensure_ascii=False, indent=2)
                    preserved_parts.append(f"[TOOL_CALL]\n{tool_info}\n[/TOOL_CALL]")
                else:
                    item_info = json.dumps(item, ensure_ascii=False, indent=2)
                    preserved_parts.append(f"[CONTENT_ITEM]\n{item_info}\n[/CONTENT_ITEM]")
            elif isinstance(item, str):
                preserved_parts.append(item)
            else:
                preserved_parts.append(str(item))
        return '\n'.join(preserved_parts)
    elif isinstance(content_data, dict):
        return json.dumps(content_data, ensure_ascii=False, indent=2)
    else:
        return str(content_data)

# 请求预处理中间件
@app.middleware("http")
async def preprocess_request(request: Request, call_next):
    """预处理请求，保留所有信息"""
    if request.url.path == "/v1/chat/completions" and request.method == "POST":
        try:
            body = await request.body()
            if body:
                data = json.loads(body)
                # 预处理messages格式，保留所有信息
                if "messages" in data:
                    for message in data["messages"]:
                        if "content" in message and not isinstance(message["content"], str):
                            message["content"] = preserve_all_content(message["content"])
                            logger.info(f"Converted content for role {message.get('role', 'unknown')}")
                # 重新构造request
                new_body = json.dumps(data, ensure_ascii=False).encode('utf-8')
                async def receive():
                    return {"type": "http.request", "body": new_body}
                request._receive = receive
        except Exception as e:
            logger.error(f"Error preprocessing request: {e}")
    response = await call_next(request)
    return response

# 初始化Poe客户端
try:
    poe_client = PoeClient(Config.POE_API_KEY)
    logger.info("Poe client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Poe client: {e}")
    poe_client = None

@app.get("/")
async def root():
    return {
        "message": "OpenAI Compatible API Proxy to Poe",
        "version": "2.1.0",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "models": "/v1/models",
            "health": "/health",
            "conversations": "/v1/chat/conversations"
        },
        "features": [
            "Direct Poe model names (no mapping)",
            "Auto function calling via OpenHands prompt injection",
            "Full logging with date-based files",
            "Conversation/session API for auto multi-turn chat",
            "Conversation API supports streaming (流式多轮)"
        ],
        "status": "ready" if poe_client else "error - poe client not initialized"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy" if poe_client else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "poe_client": "initialized" if poe_client else "failed"
    }

@app.get("/v1/models", response_model=ModelListResponse)
async def list_models(api_key: str = Depends(verify_api_key)):
    """列出可用的Poe模型"""
    models_data = []
    for model_info in Config.POE_MODELS:
        models_data.append(ModelInfo(
            id=model_info["id"],
            object=model_info["object"],
            created=model_info["created"],
            owned_by=model_info["owned_by"]
        ))
    return ModelListResponse(data=models_data)

async def create_stream_response(request: ChatCompletionRequest, api_key: str):
    """创建流式响应"""
    if not poe_client:
        raise HTTPException(status_code=500, detail="Poe client not initialized")
    start_time = time.time()
    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_time = int(time.time())
    # 转换消息格式
    messages = []
    for msg in request.messages:
        msg_dict = {"role": msg.role.value}
        if msg.content is not None:
            msg_dict["content"] = msg.content
        if msg.function_call:
            msg_dict["function_call"] = msg.function_call.model_dump()
        if msg.tool_calls:
            msg_dict["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
        if msg.name:
            msg_dict["name"] = msg.name
        if msg.tool_call_id:
            msg_dict["tool_call_id"] = msg.tool_call_id
        messages.append(msg_dict)
    full_response = ""
    async def generate():
        nonlocal full_response
        try:
            async for chunk in poe_client.get_response_stream(messages, request.model):
                if chunk:
                    full_response += chunk
                    stream_response = ChatCompletionStreamResponse(
                        id=request_id,
                        created=created_time,
                        model=request.model,
                        choices=[ChatCompletionStreamChoice(
                            index=0,
                            delta={"content": chunk},
                            finish_reason=None
                        )]
                    )
                    yield f"data: {stream_response.model_dump_json()}\n\n"
            # 发送结束标记
            final_response = ChatCompletionStreamResponse(
                id=request_id,
                created=created_time,
                model=request.model,
                choices=[ChatCompletionStreamChoice(
                    index=0,
                    delta={},
                    finish_reason="stop"
                )]
            )
            yield f"data: {final_response.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
            # 记录完整的流式响应
            end_time = time.time()
            request_data = request.model_dump()
            request_logger.log_stream_request_response(
                request_data, full_response, end_time - start_time
            )
        except Exception as e:
            logger.error(f"Error in stream response: {e}")
            error_response = {
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": "internal_error"
                }
            }
            yield f"data: {json.dumps(error_response)}\n\n"
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@app.post("/v1/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key)
):
    """创建聊天完成"""
    if not poe_client:
        raise HTTPException(status_code=500, detail="Poe client not initialized")
    start_time = time.time()
    logger.info(f"Received request for Poe model: {request.model}")
    logger.info(f"Messages count: {len(request.messages)}")
    logger.info(f"Has tools: {bool(request.tools)}")
    logger.info(f"Has functions: {bool(request.functions)}")
    # 流式响应
    if request.stream:
        return await create_stream_response(request, api_key)
    # 非流式响应
    try:
        # 转换消息格式，保留所有信息
        messages = []
        for msg in request.messages:
            msg_dict = {"role": msg.role.value}
            if msg.content is not None:
                msg_dict["content"] = msg.content
            if msg.function_call:
                msg_dict["function_call"] = msg.function_call.model_dump()
            if msg.tool_calls:
                msg_dict["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
            if msg.name:
                msg_dict["name"] = msg.name
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            messages.append(msg_dict)
        logger.info(f"Processed messages with tools: {[{'role': m['role'], 'has_content': bool(m.get('content')), 'has_tools': bool(m.get('tool_calls') or m.get('function_call'))} for m in messages]}")
        response_content = await poe_client.get_response_complete(messages, request.model)
        # 构造OpenAI格式响应
        response = ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            created=int(time.time()),
            model=request.model,
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatMessage(role=Role.ASSISTANT, content=response_content),
                finish_reason="stop"
            )],
            usage=ChatCompletionUsage(
                prompt_tokens=sum(len(str(msg.get('content', '')).split()) for msg in messages),
                completion_tokens=len(response_content.split()),
                total_tokens=sum(len(str(msg.get('content', '')).split()) for msg in messages) + len(response_content.split())
            )
        )
        # 记录请求和响应
        end_time = time.time()
        request_logger.log_request_response(
            request.model_dump(),
            response.model_dump(),
            end_time - start_time
        )
        logger.info(f"Response generated successfully, length: {len(response_content)}")
        return response
    except Exception as e:
        logger.error(f"Error in chat completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== 多轮对话API ==========

class ConversationCreateRequest(BaseModel):
    system_prompt: str = None

class AddMessageRequest(BaseModel):
    role: str
    content: str
    model: str = "ChatGPT-4o-Latest"
    stream: bool = False  # 支持流式

@app.post("/v1/chat/conversations")
async def create_conversation_api(request: ConversationCreateRequest = Body(...)):
    conversation_id = conversation_manager.create_conversation(request.system_prompt)
    return {"conversation_id": conversation_id}

@app.get("/v1/chat/conversations/{conversation_id}/messages")
async def get_conversation_history(conversation_id: str = Path(...)):
    try:
        messages = conversation_manager.get_messages(conversation_id)
        return {"conversation_id": conversation_id, "messages": messages}
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")

async def create_conversation_stream_response(conversation_id, user_role, user_content, model):
    # 1. 追加用户消息
    conversation_manager.append_message(conversation_id, user_role, user_content)
    # 2. 获取全部历史
    messages = conversation_manager.get_messages(conversation_id)
    chat_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
    ]
    full_response = ""
    async def generate():
        nonlocal full_response
        try:
            async for chunk in poe_client.get_response_stream(chat_messages, model):
                if chunk:
                    full_response += chunk
                    # 简单SSE格式
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            # 结束标记
            yield f"data: {json.dumps({'content': '', 'finish_reason': 'stop'})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    # 3. 追加助手回复（等待流式结束后）
    async def append_assistant_once():
        nonlocal full_response
        async for _ in poe_client.get_response_stream(chat_messages, model):
            pass
        conversation_manager.append_message(conversation_id, "assistant", full_response)
    # 启动后台任务将助手完整回复追加到历史
    asyncio.create_task(append_assistant_once())
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@app.post("/v1/chat/conversations/{conversation_id}/messages")
async def add_message_and_reply(
    conversation_id: str = Path(...),
    request: AddMessageRequest = Body(...),
    api_key: str = Depends(verify_api_key)
):
    try:
        if request.stream:
            return await create_conversation_stream_response(
                conversation_id,
                request.role,
                request.content,
                request.model
            )
        # 非流式逻辑
        conversation_manager.append_message(conversation_id, request.role, request.content)
        messages = conversation_manager.get_messages(conversation_id)
        chat_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]
        response_content = await poe_client.get_response_complete(chat_messages, request.model)
        conversation_manager.append_message(conversation_id, "assistant", response_content)
        return {
            "conversation_id": conversation_id,
            "reply": response_content
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def start_server():
    """启动服务器"""
    print("=" * 60)
    print("🚀 OpenAI Compatible API Proxy to Poe v2.1")
    print("=" * 60)
    print(f"📡 服务地址: http://{Config.HOST}:{Config.PORT}")
    print(f"📋 API文档: http://{Config.HOST}:{Config.PORT}/docs")
    print(f"🔧 ReDoc文档: http://{Config.HOST}:{Config.PORT}/redoc")
    print("=" * 60)
    print("🎯 主要接口:")
    print(f"   • 聊天完成: POST http://{Config.HOST}:{Config.PORT}/v1/chat/completions")
    print(f"   • 模型列表: GET  http://{Config.HOST}:{Config.PORT}/v1/models")
    print(f"   • 健康检查: GET  http://{Config.HOST}:{Config.PORT}/health")
    print(f"   • 会话管理: POST/GET http://{Config.HOST}:{Config.PORT}/v1/chat/conversations")
    print("=" * 60)
    print("📊 支持的Poe模型:")
    for model in Config.POE_MODELS:
        print(f"   • {model['id']} ({model['owned_by']})")
    print("=" * 60)
    print(f"💾 日志目录: {Config.LOG_DIR}")
    print(f"🔑 环境变量 OPENAI_API_KEY: {Config.OPENAI_API_KEY}")
    print("=" * 60)
    print("✨ 新特性:")
    print("   • 直接使用Poe模型名称（无映射）")
    print("   • OpenHands自动注入函数调用提示词")
    print("   • 完整的结构化内容处理")
    print("   • 自动角色转换 (assistant ↔ bot)")
    print("   • 内置多轮会话API（自动维护历史）")
    print("   • 会话API支持流式多轮（SSE）")
    print("=" * 60)
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info"
    )

if __name__ == "__main__":
    start_server()