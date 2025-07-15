import sys
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from logger import request_logger

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpenAI Compatible API Proxy to Poe & OpenAI",
    description="A proxy service that supports OpenAI-compatible API forwarding to Poe/OpenAI",
    version="2.3.0"
)

# CORS
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

# 路由注册
from routes_misc import register_misc_routes
from routes_chat import register_chat_routes

register_misc_routes(app)
register_chat_routes(app)

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

if __name__ == "__main__":
    start_server()