import os

class Config:
    POE_API_KEY = "xxxxx-xxxxx-xxxxx-xxxxx"  # 替换为你的Poe API密钥
    # echo $OPENAI_API_KEY
    # export OPENAI_API_KEY="your-api-key-here"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-dummy-key-for-compatibility")
    HOST = "0.0.0.0"
    PORT = 8000
    LOG_DIR = "train_data"
    
    # 直接使用Poe的模型名称，无需映射
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