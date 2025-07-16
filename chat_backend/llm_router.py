import logging
from enum import Enum
from config import Config

# 各 LLM 客户端
from poe_client import PoeClient
from openai_client import OpenAIClient

logger = logging.getLogger(__name__)

class LLMBackend(str, Enum):
    POE = "poe"
    OPENAI = "openai"

def get_llm_backend():
    return getattr(Config, "LLM_BACKEND", "poe").lower()

def get_llm_client():
    backend = get_llm_backend()
    if backend == LLMBackend.POE:
        return PoeClient(Config.POE_API_KEY), LLMBackend.POE
    elif backend == LLMBackend.OPENAI:
        return OpenAIClient(Config.OPENAI_API_KEY), LLMBackend.OPENAI
    else:
        logger.warning("Unknown LLM_BACKEND '%s', fallback to poe.", backend)
        return PoeClient(Config.POE_API_KEY), LLMBackend.POE