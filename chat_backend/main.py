import sys
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# === 确保项目根目录在 sys.path 中 ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# === 本地模块导入 ===
from config import Config
from logger import request_logger
from routes_misc import register_misc_routes
from routes_project import router as project_router
from routes.chat import register_chat_routes 


# === FastAPI App 初始化 ===
app = FastAPI(
    title="OpenAI Compatible API Proxy to Poe & OpenAI",
    description="A proxy service that supports OpenAI-compatible API forwarding to Poe/OpenAI",
    version="2.3.0"
)
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print("==== 发生未捕获异常 ====")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
# === CORS 设置 ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 注册路由 ===
register_misc_routes(app)
register_chat_routes(app)
app.include_router(project_router)

from routes.routes_plan import router as plan_router
app.include_router(plan_router)

# === 启动函数 ===
def start_server():
    import uvicorn
    print("=" * 60)
    print("🚀 OpenAI Compatible API Proxy (Poe/OpenAI)")
    print("=" * 60)
    print(f"📡 服务地址: http://{Config.HOST}:{Config.PORT}")
    print(f"🧩 LLM后端: {Config.LLM_BACKEND}")
    print("=" * 60)
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info"
    )

# === CLI 启动入口 ===
if __name__ == "__main__":
    start_server()
