import logging
import asyncio
from typing import Any, Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class QueryTimeoutError(Exception):
    """Raised when a query execution exceeds its allocated time limit."""
    pass

class TimeoutProtection:
    """
    Enforces execution time limits on database operations.
    Prevents single queries from hanging the backend or overloading the DB.
    """

    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(self, max_timeout: int = DEFAULT_TIMEOUT):
        self.max_timeout = max_timeout
        # Thread pool for running synchronous DB calls with timeouts
        self._executor = ThreadPoolExecutor(max_workers=10)

    async def run_with_timeout(
        self, 
        func: Callable[..., Any], 
        *args, 
        timeout_seconds: int = None, 
        **kwargs
    ) -> Any:
        """
        Execute a function with a strict timeout.
        
        Args:
            func: The function to execute.
            timeout_seconds: Timeout in seconds (falls back to default).
            
        Returns:
            The result of func(*args, **kwargs).
            
        Raises:
            QueryTimeoutError: If execution exceeds the timeout.
        """
        timeout = min(timeout_seconds or self.DEFAULT_TIMEOUT, self.max_timeout)
        
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            else:
                # For synchronous functions (like SQLAlchemy execute)
                loop = asyncio.get_running_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(self._executor, lambda: func(*args, **kwargs)),
                    timeout=timeout
                )
        except asyncio.TimeoutError:
            logger.error(f"TimeoutProtection: execution exceeded {timeout}s limit.")
            raise QueryTimeoutError(f"Query execution timed out after {timeout} seconds.")
        except Exception as exc:
            logger.error(f"TimeoutProtection: execution failed — {exc}")
            raise
