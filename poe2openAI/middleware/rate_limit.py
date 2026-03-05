import time
from collections import defaultdict
from typing import Dict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from config import Config


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rpm: int = Config.RATE_LIMIT_RPM):
        super().__init__(app)
        self.rpm = rpm
        self.requests: Dict[str, list] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/v1/"):
            api_key = request.headers.get("authorization", "").replace("Bearer ", "")
            if api_key:
                now = time.time()
                minute_ago = now - 60
                
                self.requests[api_key] = [t for t in self.requests[api_key] if t > minute_ago]
                
                if len(self.requests[api_key]) >= self.rpm:
                    reset_time = int(self.requests[api_key][0] + 60 - now)
                    return HTTPException(
                        status_code=429,
                        detail={
                            "error": {
                                "message": "Rate limit exceeded",
                                "type": "rate_limit_error",
                                "code": "rate_limit_exceeded",
                            }
                        },
                        headers={
                            "Retry-After": str(reset_time),
                            "X-RateLimit-Limit-Requests": str(self.rpm),
                            "X-RateLimit-Remaining-Requests": "0",
                            "X-RateLimit-Reset-Requests": str(reset_time),
                        }
                    )
                
                self.requests[api_key].append(now)

        response = await call_next(request)
        
        if request.url.path.startswith("/v1/"):
            api_key = request.headers.get("authorization", "").replace("Bearer ", "")
            if api_key and api_key in self.requests:
                remaining = max(0, self.rpm - len(self.requests[api_key]))
                response.headers["X-RateLimit-Limit-Requests"] = str(self.rpm)
                response.headers["X-RateLimit-Remaining-Requests"] = str(remaining)
                if self.requests[api_key]:
                    reset_time = int(self.requests[api_key][0] + 60 - time.time())
                    response.headers["X-RateLimit-Reset-Requests"] = str(max(0, reset_time))

        return response