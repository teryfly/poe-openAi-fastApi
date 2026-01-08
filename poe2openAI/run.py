#!/usr/bin/env python3
"""
启动脚本 - 支持永不超时配置和增强的资源管理
"""
import os
import sys
import signal
import asyncio
import uvicorn
from typing import Optional
import logging

# 设置日志（格式由 main.py 或入口处的 basicConfig 统一控制）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger(__name__)


class CustomUvicornServer:
    """自定义 Uvicorn 服务器，支持永不超时和优雅关闭"""

    def __init__(self):
        self.server: Optional[uvicorn.Server] = None
        self.should_exit = False

    def setup_signal_handlers(self):
        """设置信号处理器"""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.should_exit = True
            if self.server:
                self.server.should_exit = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run_server(self):
        """运行服务器"""
        from config import Config

        # 创建 uvicorn 配置（不再覆盖 log_config，使用全局 basicConfig）
        config = uvicorn.Config(
            "main:app",
            host=Config.HOST,
            port=Config.PORT,
            log_level="info",
            access_log=True,
            reload=False,  # 在生产环境中禁用 reload
            timeout_keep_alive=Config.TIMEOUT_KEEP_ALIVE,
            timeout_graceful_shutdown=Config.TIMEOUT_GRACEFUL_SHUTDOWN,
            # 禁用各种超时限制
            timeout_notify=0,  # 禁用通知超时
            limit_concurrency=None,  # 无并发限制
            limit_max_requests=None,  # 无最大请求限制
            backlog=2048,  # 增大连接队列
            # HTTP 配置
            h11_max_incomplete_event_size=None,  # 无限制
        )
        self.server = uvicorn.Server(config)
        logger.info("Starting server with enhanced configuration...")
        logger.info(f"Keep-alive timeout: {Config.TIMEOUT_KEEP_ALIVE} (0 = infinite)")
        logger.info(
            f"Graceful shutdown timeout: {Config.TIMEOUT_GRACEFUL_SHUTDOWN}s"
        )
        logger.info("HTTP timeout: 0 (infinite or configured at upstream)")

        try:
            await self.server.serve()
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
        finally:
            logger.info("Server stopped")

    def run(self):
        """运行服务器的同步入口点"""
        self.setup_signal_handlers()
        try:
            asyncio.run(self.run_server())
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sys.exit(1)


def print_startup_banner():
    """打印启动横幅"""
    from config import Config

    print("=" * 80)
    print("🚀 OpenAI Compatible API Proxy to Poe v2.1 - Enhanced Edition")
    print("=" * 80)
    print(f"📡 服务地址: http://{Config.HOST}:{Config.PORT}")
    print(f"📋 API文档: http://{Config.HOST}:{Config.PORT}/docs")
    print(f"🔧 ReDoc文档: http://{Config.HOST}:{Config.PORT}/redoc")
    print("=" * 80)
    print("🎯 主要接口:")
    print(f"   • 聊天完成: POST http://{Config.HOST}:{Config.PORT}/v1/chat/completions")
    print(f"   • 模型列表: GET  http://{Config.HOST}:{Config.PORT}/v1/models")
    print(f"   • 健康检查: GET  http://{Config.HOST}:{Config.PORT}/health")
    print("=" * 80)
    print("📊 支持的Poe模型:")
    for i, model in enumerate(Config.POE_MODELS[:5]):  # 只显示前5个
        print(f"   • {model['id']} ({model['owned_by']})")
    if len(Config.POE_MODELS) > 5:
        print(f"   • ... 以及其他 {len(Config.POE_MODELS) - 5} 个模型")
    print("=" * 80)
    print(f"💾 日志目录: {Config.LOG_DIR}")
    print(
        f"🔑 API密钥配置: {'✓ 已设置' if Config.OPENAI_API_KEY != 'sk-test-key-for-compatibility-Test' else '⚠ 使用测试密钥'}"
    )
    print(
        f"🔌 Poe API密钥: {'✓ 已配置' if Config.POE_API_KEY != 'xxx-xxx-xxx-xxx' else '❌ 需要配置'}"
    )
    print("=" * 80)
    print("✨ 增强特性:")
    print("   • 直接使用Poe模型名称（无映射）")
    print("   • OpenHands自动注入函数调用提示词")
    print("   • 完整的结构化内容处理")
    print("   • 自动角色转换 (assistant ↔ bot)")
    print("   • 🆕 增强的异步生成器处理")
    print("   • 🆕 永不超时配置 (Keep-alive: ∞)")
    print("   • 🆕 优雅关闭和资源清理")
    print("   • 🆕 防止异步生成器重复关闭")
    print("=" * 80)
    print("🔧 服务器配置:")
    print(
        f"   • Keep-alive 超时: {Config.TIMEOUT_KEEP_ALIVE} "
        f"{'(永不超时)' if Config.TIMEOUT_KEEP_ALIVE == 0 else '秒'}"
    )
    print(f"   • 优雅关闭超时: {Config.TIMEOUT_GRACEFUL_SHUTDOWN} 秒")
    print("   • HTTP 超时: 0 (无限制)")
    print("   • 连接队列: 2048")
    print("   • 并发限制: 无限制")
    print("=" * 80)
    # 检查配置
    if Config.POE_API_KEY == "xxx-xxx-xxx-xxx":
        print("⚠️  警告: 请在 config.py 中设置正确的 POE_API_KEY")
        print("=" * 80)


def main():
    """主启动函数"""
    print("🔧 正在启动OpenAI兼容API代理服务...")
    # 检查和创建必要的目录
    try:
        from config import Config

        os.makedirs(Config.LOG_DIR, exist_ok=True)
        logger.info(f"Log directory ensured: {Config.LOG_DIR}")
    except Exception as e:
        logger.error(f"Failed to create log directory: {e}")
        sys.exit(1)
    # 打印启动信息
    print_startup_banner()
    # 检查必要的依赖
    try:
        import fastapi  # noqa: F401
        import fastapi_poe  # noqa: F401
        import uvicorn  # noqa: F401

        logger.info("All dependencies are available")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Please install requirements: pip install -r requirements.txt")
        sys.exit(1)
    # 启动增强服务器
    server = CustomUvicornServer()
    server.run()


if __name__ == "__main__":
    main()