import os

class Config:
    POE_API_KEY = "xxx-xxx-xxx-xxx"  # 替换为你的Poe API密钥
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-test-key-for-compatibility-Test")
    HOST = "0.0.0.0"
    PORT = 8000
    LOG_DIR = "train_data"
    
    # 直接使用Poe的模型名称，无需映射
    POE_MODELS = [
        {
            "id": "GPT-4.1",
            "object": "model",
            "created": 1715368132,
            "owned_by": "openai",
            "description": "OpenAI’s latest flagship model with significantly improved coding skills, long context (1M tokens), and improved instruction following."
        },
        {
            "id": "Claude-Sonnet-4-Reasoning",
            "object": "model",
            "created": 1729641602,
            "owned_by": "anthropic",
            "description": "Claude Sonnet 4 from Anthropic, supports customizable thinking budget (up to 60k tokens) and 200k context window.To instruct the bot to use more thinking effort, add --thinking_budget and a number ranging from 0 to 16,384 to the end of your message."
        },
        {
            "id": "Claude-Sonnet-4",
            "object": "model",
            "created": 1729641600,
            "owned_by": "anthropic",
            "description": "Anthropic's Claude 4 Sonnet using the 2025 model snapshot"
        },
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
