from fastapi import Depends, APIRouter
from fastapi.responses import JSONResponse
from datetime import datetime
from config import Config
from models import ModelInfo, ModelListResponse
from llm_router import get_llm_backend

def register_misc_routes(app):
    router = APIRouter()

    @router.get("/")
    async def root():
        return {
            "message": "OpenAI Compatible API Proxy to Poe or OpenAI",
            "version": "2.3.0",
            "llm_backend": get_llm_backend(),
            "endpoints": {
                "chat_completions": "/v1/chat/completions",
                "models": "/v1/models",
                "health": "/health",
                "conversations": "/v1/chat/conversations"
            }
        }

    @router.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "llm_backend": get_llm_backend()
        }

    @router.get("/v1/models", response_model=ModelListResponse)
    async def list_models():
        models_data = []
        for model_info in Config.POE_MODELS:
            models_data.append(ModelInfo(
                id=model_info["id"],
                object=model_info["object"],
                created=model_info["created"],
                owned_by=model_info["owned_by"]
            ))
        return ModelListResponse(data=models_data)

    app.include_router(router)