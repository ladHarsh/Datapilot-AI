import logging
import time
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Prevents brute-force and DDoS attacks by limiting request frequency per IP.
    In production, this should use Redis for distributed rate limiting.
    """

    # 100 requests per minute per IP
    RATE_LIMIT = 100
    WINDOW_SECONDS = 60

    def __init__(self, app):
        super().__init__(app)
        self._request_counts = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = time.time()
        
        # Cleanup old requests outside the window
        self._request_counts[client_ip] = [
            t for t in self._request_counts[client_ip] 
            if now - t < self.WINDOW_SECONDS
        ]
        
        if len(self._request_counts[client_ip]) >= self.RATE_LIMIT:
            logger.warning(f"RateLimitMiddleware: rate limit exceeded for IP {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."}
            )
            
        self._request_counts[client_ip].append(now)
        return await call_next(request)
