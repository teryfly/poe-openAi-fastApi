import logging
from datetime import datetime

import uvicorn
from config import Config
from api.app_factory import create_app

# 配置全局日志格式：ISO8601 时间戳、级别、模块名、消息
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

app = create_app()


def start_server():
    # 在横幅之前打印当前时间（ISO8601）
    current_time = datetime.now().isoformat()
    print(f"Current time: {current_time}")

    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        log_level="info",
        timeout_keep_alive=Config.TIMEOUT_KEEP_ALIVE,
        timeout_graceful_shutdown=Config.TIMEOUT_GRACEFUL_SHUTDOWN,
    )


if __name__ == "__main__":
    start_server()