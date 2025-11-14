import os
class Config:
    POE_API_KEY = "xxx-xxx-xxx-xxx"  # 替换为你的Poe API密钥
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-test-key-for-compatibility-Test")
    HOST = "0.0.0.0"
    PORT = 8000
    LOG_DIR = "train_data"
    # 超时配置 - 设置为永不超时
    TIMEOUT_KEEP_ALIVE = 0  # 0 表示永不超时
    TIMEOUT_GRACEFUL_SHUTDOWN = 300  # 优雅关闭超时时间
    TIMEOUT_HTTP = 0  # HTTP 请求超时，0 表示无限制

    # 附件相关配置
    ATTACHMENTS_DIR = os.getenv("ATTACHMENTS_DIR", "attachments")
    ATTACHMENT_MAX_SIZE_MB = float(os.getenv("ATTACHMENT_MAX_SIZE_MB", "20"))  # 单文件最大MB
    ATTACHMENT_ALLOWED_TYPES = set(
        (os.getenv("ATTACHMENT_ALLOWED_TYPES", "image/png,image/jpeg,image/webp,application/pdf")).split(",")
    )
    ATTACHMENT_BASE_URL = os.getenv("ATTACHMENT_BASE_URL", "")  # 若前置有反向代理提供文件服务，可设置为 http(s)://host/path

    # 直接使用Poe的模型名称，无需映射
    POE_MODELS = [
        {
            "id": "Qwen3-Coder",
            "object": "model",
            "created": 131536811,
            "owned_by": "300",
            "description": "400k tokens) "
        }, 
        {
            "id": "GPT-OSS-120B-T",
            "object": "model",
            "created": 1715368130,
            "owned_by": "openai/50",
            "description": "GPT-OSS-120B-T is an open-source model trained on a diverse range of internet text, designed to generate human-like text based on the input it receives. It excels in various natural language processing tasks, including text generation, summarization, and translation."
        },
       {
            "id": "GPT-5.1",
            "object": "model",
            "created": 171536813,
            "owned_by": "openai/38/38/300",
            "description": "400k tokens) "
        }, 
        {
            "id": "GPT-5-Codex",
            "object": "model",
            "created": 181536813,
            "owned_by": "openai/38/38/300",
            "description": "400k tokens) "
        }, 
        {
            "id": "GPT-5-Pro",
            "object": "model",
            "created": 181536818,
            "owned_by": "openai/450/3600",
            "description": "400k tokens) "
        }, 
        {
            "id": "GPT-5",
            "object": "model",
            "created": 171536814,
            "owned_by": "openai/38/38/300",
            "description": "400k tokens) "
        },   
        {
            "id": "GPT-4.1",
            "object": "model",
            "created": 1715368132,
            "owned_by": "openai/60/60/193",
            "description": "long context (1M tokens)"
        }, 
        {
            "id": "Claude-Sonnet-4-Reasoning",
            "object": "model",
            "created": 1729641602,
            "owned_by": "anthropic/115/115/1695",
            "description": "Claude Sonnet 4 from Anthropic, supports customizable thinking budget (up to 60k tokens) and 200k context window.To instruct the bot to use more thinking effort, add --thinking_budget and a number ranging from 0 to 16,384 to the end of your message."
        },
        {
            "id": "Claude-Sonnet-4",
            "object": "model",
            "created": 1729641600,
            "owned_by": "anthropic/115/115/911",
            "description": "Anthropic's Claude 4 Sonnet using the 2025 model snapshot"
        },
        {
            "id": "Claude-Sonnet-4.5",
            "object": "model",
            "created": 1729641600,
            "owned_by": "anthropic/92/400",
            "description": "Claude Sonnet 4.5 represents a major leap forward in AI capability and alignment.  distinguished by dramatic improvements in reasoning, mathematics, and real-world coding. Supports 200k tokens of context."
        },
        {
            "id": "Claude-3.7-Sonnet",
            "object": "model",
            "created": 1729641600,
            "owned_by": "anthropic/115/115/1017",
            "description": "Anthropic's Claude 3.7,To instruct the bot to use more thinking effort, add --thinking_budget and a number ranging from 0 to 16,384 to the end of your message."
        },
        {
            "id": "Claude-3.5-Sonnet",
            "object": "model",
            "created": 1729641600,
            "owned_by": "anthropic/115/115/243",
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
            "id": "Gemini-2.5-Pro",
            "object": "model",
            "created": 1716368132,
            "owned_by": "Google/13/13/4/332",
            "description": "Gemini 2.5 Pro is Google's advanced model with frontier performance on various key benchmarks; supports web search and 1 million tokens of input context"
        },
        {
            "id": "Gemini-2.5-Flash",
            "object": "model",
            "created": 1716368133,
            "owned_by": "Google/3/3/1/8",
            "description": "Reasoning capabilities, search capabilities, and image/video understanding while still prioritizing speed and cost. Supports 1M tokens of input context."
        }, 
        {
            "id": "Gemini-1.5-Pro",
            "object": "model",
            "created": 1716368120,
            "owned_by": "Google/5/5/5/30",
            "description": ""
        }, 
        {
            "id": "o3",
            "object": "model",
            "created": 1735689600,
            "owned_by": "openai/60/60/388",
            "description": "State-of-the-art intelligence on a variety of tasks and domains"
        },
        {
            "id": "o4-mini",
            "object": "model",
            "created": 1725148800,
            "owned_by": "openai/33/33/235",
            "description": "supports 200k tokens of input context and 100k tokens of output context.To instruct the bot to use more reasoning effort, add --reasoning_effort to the end of your message with one of 'low', 'medium', or 'high'"
        },
        {
            "id": "GPT-3.5-Turbo",
            "object": "model",
            "created": 1677610602,
            "owned_by": "openai",
            "description": "GPT-3.5 Turbo model via Poe"
        }
    ]