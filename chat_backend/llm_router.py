import logging
from config import Config
from services.poe_timeout_client import ConfigurableTimeoutPoeClient

logger = logging.getLogger(__name__)

def get_llm_backend():
    """
    Returns the LLM backend type (now always 'poe')
    """
    return "poe"

def get_llm_client():
    """
    Returns the Poe client instance
    """
    return ConfigurableTimeoutPoeClient(
        api_key=Config.POE_API_KEY,
        base_url=Config.POE_BASE_URL,
        non_stream_timeout_seconds=Config.POE_NON_STREAM_TIMEOUT_SECONDS,
    ), "poe"