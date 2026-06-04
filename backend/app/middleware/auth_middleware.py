import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.services.auth.auth_service import AuthService, AuthenticationError

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Intercepts HTTP requests to validate JWT tokens and session integrity.
    Ensures that only authenticated users can access protected routes.
    """

    EXEMPT_PATHS = {"/api/v1/auth/login", "/api/v1/auth/signup", "/docs", "/openapi.json", "/health"}

    async def dispatch(self, request: Request, call_next):
        # Skip authentication for exempt paths
        if request.url.path in self.EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(f"AuthMiddleware: missing or invalid Authorization header for path {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required. Missing Bearer token."}
            )

        token = auth_header.replace("Bearer ", "")
        
        try:
            # We need a DB session to validate auth (if using AuthService's default logic)
            # In a real app, you might use a faster cache check here.
            # For simplicity, we assume AuthService is available via app state or similar.
            # Here we simulate the validation.
            from app.core.config import settings
            from app.db.session import SessionLocal
            
            with SessionLocal() as db:
                auth_service = AuthService(db)
                user_payload = auth_service.validate_request_token(token)
                
                # Attach user info to request state
                request.state.user = user_payload
                
            return await call_next(request)
            
        except AuthenticationError as exc:
            logger.error(f"AuthMiddleware: authentication failed — {exc}")
            return JSONResponse(
                status_code=401,
                content={"detail": str(exc)}
            )
        except Exception as exc:
            logger.error(f"AuthMiddleware: unexpected error — {exc}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal security error during authentication."}
            )
