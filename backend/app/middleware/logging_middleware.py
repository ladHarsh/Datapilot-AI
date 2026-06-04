import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("security_audit")

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with its security context and performance metrics.
    Essential for audit trails and debugging security incidents.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Get user from state if attached by AuthMiddleware
        user_id = getattr(request.state, "user", {}).get("sub", "anonymous")
        client_ip = request.client.host
        
        response = await call_next(request)
        
        process_time = (time.time() - start_time) * 1000
        
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "user_id": user_id,
            "ip": client_ip,
            "duration_ms": f"{process_time:.2f}ms"
        }
        
        # Log critical events or suspicious status codes
        if response.status_code >= 400:
            logger.warning(f"Security Audit: {log_data}")
        else:
            logger.info(f"Access Audit: {log_data}")
            
        return response
