import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SecureHeadersService:
    """
    Manages security-related HTTP headers for the API.
    Ensures compliance with OWASP recommendations and helps prevent 
    common attacks like XSS, Clickjacking, and MIME-sniffing.
    """

    def get_secure_headers(self) -> Dict[str, str]:
        """
        Return a dictionary of security headers to be applied to responses.
        """
        return {
            # Prevent browser from guessing MIME type (prevents certain XSS attacks)
            "X-Content-Type-Options": "nosniff",
            
            # Prevent site from being embedded in frames (prevents Clickjacking)
            "X-Frame-Options": "DENY",
            
            # Basic Content Security Policy
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; object-src 'none';",
            
            # Prevent older browsers from caching sensitive data
            "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            
            # Strict-Transport-Security (enforce HTTPS)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            
            # Referrer-Policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Permissions-Policy (restrict browser features)
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            
            # Brand protection
            "X-XSS-Protection": "1; mode=block",
        }

    def apply_to_response(self, response_headers: Any) -> None:
        """
        Apply secure headers to a FastAPI/Starlette response object.
        """
        headers = self.get_secure_headers()
        for key, value in headers.items():
            response_headers[key] = value
        logger.debug("SecureHeadersService: applied security headers to response.")
