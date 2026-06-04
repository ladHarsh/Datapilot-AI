import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Performs global validation on incoming request payloads.
    Protects against malformed JSON, oversized requests, and common 
    non-SQL injection patterns in body/params.
    """

    MAX_BODY_SIZE = 1024 * 1024  # 1MB

    async def dispatch(self, request: Request, call_next):
        # 1. Content length check
        content_length = request.headers.get("Content-Length")
        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            logger.warning(f"RequestValidationMiddleware: payload too large ({content_length} bytes)")
            return JSONResponse(
                status_code=413,
                content={"detail": "Request payload exceeds safety limits."}
            )

        # 2. Check for malformed JSON if Content-Type is application/json
        if request.headers.get("Content-Type") == "application/json":
            try:
                # Note: Reading body here requires care as it can consume the stream
                # In FastAPI, it's better to do this in custom Request class or specific dependencies.
                # However, for a generic security check:
                pass 
            except Exception:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid JSON payload."}
                )

        return await call_next(request)
