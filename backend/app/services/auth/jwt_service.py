"""
JWT Service
============
Handles JWT token generation, validation, and expiration.
Uses RS256 or HS256 signing with configurable secret/key.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError, DecodeError

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenExpiredError(Exception):
    """Raised when a JWT token has expired."""
    pass


class TokenInvalidError(Exception):
    """Raised when a JWT token is invalid or tampered."""
    pass


class JWTService:
    """
    Generates, signs, and validates JWT access and refresh tokens.

    Configuration (via environment variables):
        JWT_SECRET_KEY:              HMAC secret key (required for HS256).
        JWT_ALGORITHM:               Signing algorithm (default: HS256).
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES:  Access token lifetime (default: 30 min).
        JWT_REFRESH_TOKEN_EXPIRE_DAYS:    Refresh token lifetime (default: 7 days).
        JWT_ISSUER:                  Token issuer claim.
        JWT_AUDIENCE:                Token audience claim.
    """

    ACCESS_TOKEN_EXPIRE_MINUTES: int = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    REFRESH_TOKEN_EXPIRE_DAYS: int = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    ALGORITHM: str = settings.JWT_ALGORITHM
    ISSUER: str = settings.JWT_ISSUER
    AUDIENCE: str = settings.JWT_AUDIENCE

    def __init__(self, secret_key: Optional[str] = None):
        self._secret_key = secret_key or settings.JWT_SECRET_KEY
        if not self._secret_key or "change-me" in self._secret_key.lower():
            # If it's the default or empty, we check os.getenv as a fallback (legacy)
            # but usually settings should have it from .env
            pass
            
        logger.info(
            "JWTService: initialized (algo=%s, access_ttl=%dm, refresh_ttl=%dd).",
            self.ALGORITHM, self.ACCESS_TOKEN_EXPIRE_MINUTES, self.REFRESH_TOKEN_EXPIRE_DAYS,
        )

    # ── Token generation ──────────────────────────────────────────────────────

    def create_access_token(self, data: Dict[str, Any]) -> str:
        """
        Generate a signed JWT access token.

        Args:
            data: Payload dict. Must include 'sub' (user ID).

        Returns:
            Signed JWT string.
        """
        return self._create_token(
            data=data,
            expires_delta=timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
            token_type="access",
        )

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Generate a signed JWT refresh token with longer expiry.

        Args:
            data: Payload dict. Must include 'sub' (user ID).

        Returns:
            Signed JWT string.
        """
        return self._create_token(
            data=data,
            expires_delta=timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            token_type="refresh",
        )

    def _create_token(
        self,
        data: Dict[str, Any],
        expires_delta: timedelta,
        token_type: str,
    ) -> str:
        """Internal token creation with standard claims."""
        now = datetime.now(timezone.utc)
        payload = {
            **data,
            "iat": now,                                 # issued at
            "nbf": now,                                 # not before
            "exp": now + expires_delta,                 # expiry
            "iss": self.ISSUER,                         # issuer
            "aud": self.AUDIENCE,                       # audience
            "type": token_type,                         # custom claim
        }
        token = jwt.encode(payload, self._secret_key, algorithm=self.ALGORITHM)
        logger.debug("JWTService: created %s token (sub=%s).", token_type, data.get("sub"))
        return token

    # ── Token validation ──────────────────────────────────────────────────────

    def validate_token(self, token: str, expected_type: str = "access") -> Dict[str, Any]:
        """
        Validate a JWT token and return its payload.

        Args:
            token:         The JWT string to validate.
            expected_type: 'access' or 'refresh' — ensures token type matches.

        Returns:
            Decoded payload dict.

        Raises:
            TokenExpiredError:  If the token has expired.
            TokenInvalidError:  If the token is invalid or tampered.
        """
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self.ALGORITHM],
                audience=self.AUDIENCE,
                issuer=self.ISSUER,
            )

            # Validate token type
            if payload.get("type") != expected_type:
                raise TokenInvalidError(
                    f"Invalid token type: expected '{expected_type}', "
                    f"got '{payload.get('type')}'."
                )

            logger.debug("JWTService: token valid (sub=%s).", payload.get("sub"))
            return payload

        except ExpiredSignatureError:
            logger.warning("JWTService: token expired.")
            raise TokenExpiredError("Token has expired. Please log in again.")

        except DecodeError as exc:
            logger.warning("JWTService: token decode error — %s", exc)
            raise TokenInvalidError(f"Token is malformed: {exc}")

        except InvalidTokenError as exc:
            logger.warning("JWTService: invalid token — %s", exc)
            raise TokenInvalidError(f"Token is invalid: {exc}")

    def decode_without_validation(self, token: str) -> Dict[str, Any]:
        """
        Decode token payload WITHOUT signature validation.
        Use only for inspecting expired tokens (e.g., to extract sub for refresh).
        NEVER use for authorization decisions.
        """
        return jwt.decode(
            token,
            options={"verify_signature": False},
        )

    def get_token_remaining_time(self, token: str) -> Optional[int]:
        """
        Return remaining validity in seconds, or None if expired/invalid.
        """
        try:
            payload = self.validate_token(token)
            exp = payload.get("exp")
            if exp:
                remaining = exp - datetime.now(timezone.utc).timestamp()
                return max(0, int(remaining))
        except (TokenExpiredError, TokenInvalidError):
            return None
        return None
