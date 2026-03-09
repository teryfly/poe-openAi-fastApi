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

# === 新增写入源码路由 ===
from routes.write_source_code import router as write_source_code_router

# === 新增文档引用路由 ===
from routes.document_references import router as document_references_router
from routes.document_references_manage import router as document_references_manage_router

# === 引入重构后的计划模块路由 ===
from routes.plan import router as plan_router

# === 新增上传文件路由 ===
from routes.upload_file import router as upload_file_router

# === 新增认证路由 ===
from routes.auth import router as auth_router

# === 新增项目层级信息路由 ===
from routes.project_hierarchy import router as project_hierarchy_router

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
        "http://localhost:1573",
        "http://localhost:1572",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态目录用于附件访问（仅当未配置外部 BASE_URL 时）
from fastapi.staticfiles import StaticFiles
os.makedirs(Config.ATTACHMENTS_DIR, exist_ok=True)
if not Config.ATTACHMENT_BASE_URL:
    app.mount("/files", StaticFiles(directory=Config.ATTACHMENTS_DIR), name="files")

# === 注册路由 ===
register_misc_routes(app)
register_chat_routes(app)
app.include_router(project_router)
app.include_router(project_hierarchy_router)

# === 注册写入源码API路由 ===
app.include_router(write_source_code_router)

# === 注册文档引用API路由 ===
app.include_router(document_references_router)
app.include_router(document_references_manage_router)

# === 注册计划模块路由（分类 + 文档 + 最新列表/迁移） ===
app.include_router(plan_router)

# === 注册上传文件路由 ===
app.include_router(upload_file_router)

# === 注册认证路由 ===
app.include_router(auth_router)

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