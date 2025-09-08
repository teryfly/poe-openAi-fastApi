import logging
import uvicorn
from config import Config
from api.app_factory import create_app

logging.basicConfig(level=logging.INFO)
app = create_app()

def start_server():
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        log_level="info",
        timeout_keep_alive=Config.TIMEOUT_KEEP_ALIVE,
        timeout_graceful_shutdown=Config.TIMEOUT_GRACEFUL_SHUTDOWN
    )

if __name__ == "__main__":
    start_server()