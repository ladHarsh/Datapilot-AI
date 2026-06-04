import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.protection.secure_headers_service import SecureHeadersService

logger = logging.getLogger(__name__)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies secure HTTP headers to every outgoing response.
    """

    def __init__(self, app):
        super().__init__(app)
        self.headers_service = SecureHeadersService()

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Apply headers from service
        headers = self.headers_service.get_secure_headers()
        for key, value in headers.items():
            response.headers[key] = value
            
        return response
