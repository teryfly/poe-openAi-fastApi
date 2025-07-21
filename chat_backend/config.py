import os

class Config:
    POE_API_KEY = "xxxxx-xxxxx-xxxxx-xxxxx"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-test-key-for-compatibility-Test")
    # 新增配置：自定义 OpenAI 兼容 API 服务端 URL
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://43.132.224.225:8000/v1")
    HOST = "0.0.0.0"
    PORT = 8000
    LOG_DIR = "train_data"

    LLM_BACKEND = os.getenv("LLM_BACKEND", "openai")  # openai  or poe

    # 新增：忽略落库的用户消息内容列表（完全匹配时生效）
    ignoredUserMessages = [
        "continue, and mark [to be continue] at the last line of your replay if your output is NOT over and wait user's command to be continued",
        "continue",
        "继续",
        "go on"
    ]

    POE_MODELS = [
        {
            "id": "Claude-3.5-Sonnet",
            "object": "model",
            "created": 1729641600,
            "owned_by": "anthropic",
            "description": "Anthropic's Claude 3.5 Sonnet using the October 22, 2024 model snapshot"
        },
        {
            "id": "Claude-Sonnet-4",
            "object": "model",
            "created": 1729641601,
            "owned_by": "anthropic",
            "description": "Anthropic's Claude 4 Sonnet"
        },
        {
            "id": "Claude-Sonnet-4-Reasoning",
            "object": "model",
            "created": 1729641602,
            "owned_by": "anthropic",
            "description": "Claude Sonnet 4 from Anthropic, supports customizable thinking budget (up to 60k tokens) and 200k context window.To instruct the bot to use more thinking effort, add --thinking_budget and a number ranging from 0 to 16,384 to the end of your message."
        },
        {
            "id": "GPT-4.1",
            "object": "model",
            "created": 1715368132,
            "owned_by": "openai",
            "description": "OpenAI’s latest flagship model with significantly improved coding skills, long context (1M tokens), and improved instruction following. Supports native vision, and generally has more intelligence than GPT-4o"
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