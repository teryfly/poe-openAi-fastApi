from typing import Optional, Dict, Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse


def create_error_response(
    status_code: int,
    message: str,
    error_type: str,
    code: Optional[str] = None,
    param: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    error_detail = {
        "message": message,
        "type": error_type,
    }
    
    if code:
        error_detail["code"] = code
    if param:
        error_detail["param"] = param
    if metadata:
        error_detail["metadata"] = metadata
    
    return JSONResponse(
        status_code=status_code,
        content={"error": error_detail}
    )


def invalid_request_error(message: str, param: Optional[str] = None) -> JSONResponse:
    return create_error_response(400, message, "invalid_request_error", param=param)


def authentication_error(message: str = "Invalid API key") -> JSONResponse:
    return create_error_response(401, message, "authentication_error", code="invalid_api_key")


def insufficient_credits_error() -> JSONResponse:
    return create_error_response(402, "Insufficient credits", "insufficient_credits", code="insufficient_credits")


def permission_denied_error(message: str = "Permission denied") -> JSONResponse:
    return create_error_response(403, message, "moderation_error", code="permission_denied")


def not_found_error(message: str = "Resource not found") -> JSONResponse:
    return create_error_response(404, message, "not_found_error", code="not_found")


def timeout_error(message: str = "Request timeout") -> JSONResponse:
    return create_error_response(408, message, "timeout_error", code="timeout")


def request_too_large_error(message: str = "Request exceeds token limit") -> JSONResponse:
    return create_error_response(413, message, "request_too_large", code="context_length_exceeded")


def rate_limit_error(retry_after: Optional[int] = None) -> JSONResponse:
    response = create_error_response(429, "Rate limit exceeded", "rate_limit_error", code="rate_limit_exceeded")
    if retry_after:
        response.headers["Retry-After"] = str(retry_after)
    return response


def provider_error(message: str = "Provider error") -> JSONResponse:
    return create_error_response(500, message, "provider_error", code="provider_error")


def upstream_error(message: str = "Upstream service unavailable") -> JSONResponse:
    return create_error_response(502, message, "upstream_error", code="bad_gateway")


def overloaded_error(message: str = "Service overloaded") -> JSONResponse:
    return create_error_response(529, message, "overloaded_error", code="overloaded")