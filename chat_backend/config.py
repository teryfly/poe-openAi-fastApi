import os

class Config:
    # Poe API Configuration
    POE_API_KEY = os.getenv("POE_API_KEY", "O4M2J53VLP8RHevpM_KmqzhvR4tXj4OYgw5Trz40vXM")
    POE_BASE_URL = "https://api.poe.com"
    
    # Server Configuration
    HOST = "0.0.0.0"
    PORT = 8000
    LOG_DIR = "train_data"

    # LLM Backend (now Poe-only)
    LLM_BACKEND = "poe"

    # 忽略落库的用户消息内容列表（完全匹配时生效）
    ignoredUserMessages = [
        "continue, and mark [to be continue] at the last line of your replay if your output is NOT over and wait user's command to be continued",
        "continue",
        "继续",
        "go on",
        "Go on. If any incomplete code block (```) exists from the last output, find the/these incomplete Step(s) and regenerate it/them. Skip any steps that were already properly completed."
    ]
    
    # Poe Models - Using official Poe bot names
    POE_MODELS = [
        {
            "id": "Claude-Opus-4.6",
            "object": "model",
            "created": 1729641600,
            "owned_by": "anthropic",
            "description": "Claude Opus 4.6 - Anthropic's most advanced model for deep reasoning and complex coding"
        },
        {
            "id": "Claude-Sonnet-4.5",
            "object": "model",
            "created": 1729641600,
            "owned_by": "anthropic",
            "description": "Claude Sonnet 4.5 - Major improvements in reasoning, mathematics, and coding"
        },
        {
            "id": "Claude-Sonnet-4-Reasoning",
            "object": "model",
            "created": 1729641602,
            "owned_by": "anthropic",
            "description": "Claude Sonnet 4 with customizable thinking budget (up to 60k tokens)"
        },
        {
            "id": "Claude-Code",
            "object": "model",
            "created": 1729641500,
            "owned_by": "anthropic",
            "description": "Claude optimized for coding tasks"
        },
        {
            "id": "GPT-5.3-Codex",
            "object": "model",
            "created": 181536813,
            "owned_by": "openai",
            "description": "GPT-5.3 optimized for code generation"
        },
        {
            "id": "GPT-5.2",
            "object": "model",
            "created": 181536826,
            "owned_by": "openai",
            "description": "GPT-5.2 - Advanced reasoning and generation"
        },
        {
            "id": "GPT-5.1",
            "object": "model",
            "created": 171536813,
            "owned_by": "openai",
            "description": "GPT-5.1 with 400k token context"
        },
        {
            "id": "GPT-5-Pro",
            "object": "model",
            "created": 181536818,
            "owned_by": "openai",
            "description": "GPT-5 Pro with extended capabilities"
        },
        {
            "id": "GPT-5",
            "object": "model",
            "created": 171536814,
            "owned_by": "openai",
            "description": "GPT-5 with 400k token context"
        },
        {
            "id": "GPT-4.1",
            "object": "model",
            "created": 1715368132,
            "owned_by": "openai",
            "description": "GPT-4.1 with 1M token context"
        },
        {
            "id": "ChatGPT-4o-Latest",
            "object": "model",
            "created": 1715368132,
            "owned_by": "openai",
            "description": "Latest GPT-4o model"
        },
        {
            "id": "Gemini-3.1-Pro",
            "object": "model",
            "created": 1716368120,
            "owned_by": "google",
            "description": "Gemini 3.1 Pro"
        },
        {
            "id": "Gemini-3-Pro",
            "object": "model",
            "created": 1716368120,
            "owned_by": "google",
            "description": "Gemini 3 Pro"
        },
        {
            "id": "Gemini-3-Flash",
            "object": "model",
            "created": 1716368121,
            "owned_by": "google",
            "description": "Gemini 3 Flash - Fast and efficient"
        },
        {
            "id": "Gemini-2.5-Flash",
            "object": "model",
            "created": 1716368133,
            "owned_by": "google",
            "description": "Gemini 2.5 Flash with 1M token context"
        },
        {
            "id": "o4-mini",
            "object": "model",
            "created": 1725148800,
            "owned_by": "openai",
            "description": "o4-mini with reasoning capabilities"
        },
        {
            "id": "Minimax-M2.1",
            "object": "model",
            "created": 1735689722,
            "owned_by": "minimax",
            "description": "Minimax M2.1"
        },
        {
            "id": "Minimax-M2",
            "object": "model",
            "created": 1735689702,
            "owned_by": "minimax",
            "description": "Minimax M2"
        },
        {
            "id": "GPT-3.5-Turbo",
            "object": "model",
            "created": 1677610602,
            "owned_by": "openai",
            "description": "GPT-3.5 Turbo"
        }
    ]

    # 附件相关配置
    ATTACHMENTS_DIR = os.getenv("ATTACHMENTS_DIR", "attachments")
    ATTACHMENT_MAX_SIZE_MB = int(os.getenv("ATTACHMENT_MAX_SIZE_MB", "20"))
    ATTACHMENT_ALLOWED_TYPES = os.getenv(
        "ATTACHMENT_ALLOWED_TYPES",
        "image/png,image/jpeg,image/webp,application/pdf"
    )
    ATTACHMENT_BASE_URL = os.getenv("ATTACHMENT_BASE_URL", "").strip()