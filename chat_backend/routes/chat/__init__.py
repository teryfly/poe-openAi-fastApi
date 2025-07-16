from fastapi import FastAPI
from .completion import router as completion_router
from .conversation import router as conversation_router
from .message import router as message_router

def register_chat_routes(app: FastAPI):
    app.include_router(completion_router)
    app.include_router(conversation_router)
    app.include_router(message_router)
