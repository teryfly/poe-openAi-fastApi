from typing import Optional


class LLMServiceError(Exception):
    """
    Base exception for LLM service failures.
    """

    def __init__(self, message: str, upstream_status: Optional[int] = None):
        super().__init__(message)
        self.upstream_status = upstream_status


class LLMUpstreamNetworkError(LLMServiceError):
    """
    Network/connectivity errors when calling upstream LLM service.
    """


class LLMUpstreamTimeoutError(LLMServiceError):
    """
    Timeout errors when calling upstream LLM service.
    """


class LLMUpstreamResponseError(LLMServiceError):
    """
    Upstream returned invalid/non-usable response.
    """