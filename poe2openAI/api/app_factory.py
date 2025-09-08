import asyncio
import os
import json
import logging
import weakref
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from config import Config
from services.server_info import startup_banner
from poe_client import PoeClient

logger = logging.getLogger(__name__)

active_generators = weakref.WeakSet()

def preserve_all_content(content_data: Any) -> str:
    if isinstance(content_data, str):
        return content_data
    elif isinstance(content_data, list):
        preserved_parts = []
        for item in content_data:
            if isinstance(item, dict):
                if 'type' in item and 'text' in item:
                    preserved_parts.append(item['text'])
                elif 'image_url' in item and isinstance(item['image_url'], dict):
                    url = item['image_url'].get('url', '')
                    preserved_parts.append(f"[IMAGE_URL] {url}")
                elif 'tool' in item:
                    preserved_parts.append(f"[TOOL_CALL]{json.dumps(item, ensure_ascii=False)}[/TOOL_CALL]")
                else:
                    preserved_parts.append(f"[CONTENT_ITEM]{json.dumps(item, ensure_ascii=False)}[/CONTENT_ITEM]")
            elif isinstance(item, str):
                preserved_parts.append(item)
            else:
                preserved_parts.append(str(item))
        return '\n'.join(preserved_parts)
    elif isinstance(content_data, dict):
        return json.dumps(content_data, ensure_ascii=False)
    else:
        return str(content_data)

def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        print(startup_banner())
        logger.info("Application starting up...")
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        os.makedirs(Config.ATTACHMENTS_DIR, exist_ok=True)
        yield
        logger.info("Application shutting down...")
        for _ in range(10):
            if not active_generators:
                break
            await asyncio.sleep(1)
        logger.info("Application shutdown complete")

    app = FastAPI(
        title="OpenAI Compatible API Proxy to Poe",
        description="A proxy service that provides OpenAI-compatible API forwarding to Poe",
        version="2.2.2",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
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

    @app.middleware("http")
    async def preprocess_request(request: Request, call_next):
        if request.url.path == "/v1/chat/completions" and request.method == "POST" and (request.headers.get("content-type") or "").startswith("application/json"):
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    if "messages" in data:
                        for message in data["messages"]:
                            if "content" in message and not isinstance(message["content"], str):
                                message["content"] = preserve_all_content(message["content"])
                    new_body = json.dumps(data, ensure_ascii=False).encode('utf-8')
                    async def receive():
                        return {"type": "http.request", "body": new_body}
                    request._receive = receive
            except Exception as e:
                logger.error(f"Error preprocessing request: {e}")
        response = await call_next(request)
        return response

    try:
        app.state.poe_client = PoeClient(Config.POE_API_KEY)
        logging.getLogger("api.app_factory").info("Poe client initialized successfully")
    except Exception as e:
        logging.getLogger("api.app_factory").error(f"Failed to initialize Poe client: {e}")
        app.state.poe_client = None

    from routes.core import router as core_router
    from routes.chat import router as chat_router
    app.include_router(core_router)
    app.include_router(chat_router)

    app.state.active_generators = active_generators

    return app