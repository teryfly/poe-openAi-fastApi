import os
from datetime import datetime
from typing import List
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import Config
from models import ModelInfo, ModelListResponse

router = APIRouter()
logger = logging.getLogger(__name__)
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials.credentials.startswith("sk-"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    return credentials.credentials

@router.get("/")
async def root():
    return {
        "message": "OpenAI Compatible API Proxy to Poe",
        "version": "2.2.2",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "models": "/v1/models",
            "health": "/health",
            "files": "/files/{filename}"
        },
        "features": [
            "Direct Poe model names (no mapping)",
            "Auto function calling via OpenHands prompt injection",
            "Full logging with date-based files",
            "Enhanced async generator handling",
            "No timeout limits",
            "Multipart attachments (images, pdf, etc) with text"
        ],
    }

@router.get("/health")
async def health_check(request: Request):
    poe_client = getattr(request.app.state, "poe_client", None)
    active_generators = getattr(request.app.state, "active_generators", [])
    return {
        "status": "healthy" if poe_client else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "poe_client": "initialized" if poe_client else "failed",
        "active_generators": len(active_generators),
    }

@router.get("/files/{filename}")
async def get_file(filename: str):
    path = os.path.join(Config.ATTACHMENTS_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)

@router.get("/v1/models", response_model=ModelListResponse)
async def list_models(api_key: str = Depends(verify_api_key)):
    models_data: List[ModelInfo] = []
    for model_info in Config.POE_MODELS:
        models_data.append(ModelInfo(
            id=model_info["id"],
            object=model_info["object"],
            created=model_info["created"],
            owned_by=model_info["owned_by"]
        ))
    return ModelListResponse(data=models_data)