import logging
from datetime import datetime, timezone
from typing import Set

logger = logging.getLogger(__name__)

class TokenBlacklistService:
    """
    Manages a blacklist of invalidated JWT tokens (e.g., after logout).
    Ensures that stolen or logged-out tokens cannot be reused.
    """

    def __init__(self):
        # In production, use Redis with TTL for automatic cleanup
        self._blacklist: Set[str] = set()

    def blacklist_token(self, token: str) -> None:
        """Add a token to the blacklist."""
        self._blacklist.add(token)
        logger.info("TokenBlacklistService: token successfully blacklisted.")

    def is_token_blacklisted(self, token: str) -> bool:
        """Check if a token is in the blacklist."""
        return token in self._blacklist

    def cleanup_expired_tokens(self):
        """
        Stub for periodic cleanup of tokens that would have expired anyway.
        If using Redis, this is handled by TTL.
        """
        pass
