import logging
import time
from collections import defaultdict
from typing import Dict, List

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Core logic for request rate limiting.
    Supports sliding window algorithm for high accuracy.
    """

    def __init__(self, limit: int = 100, window: int = 60):
        self.limit = limit
        self.window = window
        self._history = defaultdict(list)

    def is_allowed(self, identifier: str) -> bool:
        """
        Check if the identifier (e.g. IP or UserID) is within limits.
        """
        now = time.time()
        
        # Cleanup old entries
        self._history[identifier] = [
            t for t in self._history[identifier] 
            if now - t < self.window
        ]
        
        if len(self._history[identifier]) >= self.limit:
            logger.warning(f"RateLimiter: limit reached for {identifier}")
            return False
            
        self._history[identifier].append(now)
        return True

    def get_remaining(self, identifier: str) -> int:
        return max(0, self.limit - len(self._history[identifier]))
