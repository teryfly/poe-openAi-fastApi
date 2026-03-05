import logging
from config import Config
from poe_client import PoeClient

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
    return PoeClient(Config.POE_API_KEY, Config.POE_BASE_URL), "poe"