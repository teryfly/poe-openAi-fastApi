import os

class Config:
    POE_API_KEY = "xxxxx-xxxxx-xxxxx-xxxxx"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-test-key-for-compatibility")
    # 新增配置：自定义 OpenAI 兼容 API 服务端 URL
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://43.132.224.225:8000/v1")
    HOST = "0.0.0.0"
    PORT = 8000
    LOG_DIR = "train_data"

    LLM_BACKEND = os.getenv("LLM_BACKEND", "openai")  # openai  or poe

    POE_MODELS = [
        {
            "id": "Claude-3.5-Sonnet",
            "object": "model",
            "created": 1729641600,
            "owned_by": "anthropic",
            "description": "Anthropic's Claude 3.5 Sonnet using the October 22, 2024 model snapshot"
        },
        {
            "id": "ChatGPT-4o-Latest",
            "object": "model",
            "created": 1715368132,
            "owned_by": "openai",
            "description": "Dynamic model continuously updated to the current version of GPT-4o"
        },
        {
            "id": "o3",
            "object": "model",
            "created": 1735689600,
            "owned_by": "openai",
            "description": "State-of-the-art intelligence on a variety of tasks and domains"
        },
        {
            "id": "o1-mini",
            "object": "model",
            "created": 1725148800,
            "owned_by": "openai",
            "description": "Small version of OpenAI's o1 model with better performance profile"
        },
        {
            "id": "GPT-3.5-Turbo",
            "object": "model",
            "created": 1677610602,
            "owned_by": "openai",
            "description": "GPT-3.5 Turbo model via Poe"
        }
    ]