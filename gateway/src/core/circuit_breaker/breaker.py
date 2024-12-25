from datetime import datetime, UTC
import asyncio
from typing import Dict, Any, Optional, Callable, TypeVar, Awaitable
import logging
from asyncio import Lock

from .models import CircuitState, CircuitStats, CircuitConfig, CircuitContext
from .exceptions import CircuitOpenError, ServiceUnavailableError

logger = logging.getLogger(__name__)

T = TypeVar('T')  # Return type for wrapped functions

class CircuitBreaker:
    def __init__(self, name: str, config: Optional[CircuitConfig] = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.stats = CircuitStats()
        self.state = CircuitState.CLOSED
        self.last_state_change = datetime.now(UTC)
        self._lock = Lock()
        self._half_open_count = 0
        self._consecutive_successes = 0

    async def __call__(
        self,
        func: Callable[..., Awaitable[T]],
        context: CircuitContext,
        **kwargs
    ) -> T:
        """
        Execute the wrapped function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            context: Execution context
            **kwargs: Arguments to pass to func
            
        Returns:
            Result from func if successful
            
        Raises:
            CircuitOpenError: If circuit is open
            ServiceUnavailableError: If service call fails
        """
        async with self._lock:
            await self._before_call()
            
        try:
            result = await func(**kwargs)
            await self._on_success()
            return result
            
        except Exception as e:
            await self._on_failure(e, context)
            raise ServiceUnavailableError(
                service_name=self.name,
                reason=str(e)
            ) from e

    async def _before_call(self) -> None:
        """Check circuit state before making call."""
        now = datetime.now(UTC)
        
        if self.state == CircuitState.OPEN:
            recovery_time = self.last_state_change.timestamp() + self.config.recovery_timeout
            
            if now.timestamp() > recovery_time:
                # Try recovery
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                self._half_open_count = 0
                self._consecutive_successes = 0
                logger.info(f"Circuit {self.name} entering half-open state")
            else:
                raise CircuitOpenError(
                    service_name=self.name,
                    until=datetime.fromtimestamp(recovery_time).isoformat()
                )
                
        elif self.state == CircuitState.HALF_OPEN:
            if self._half_open_count >= self.config.min_throughput:
                # Max attempts reached without full recovery
                raise CircuitOpenError(self.name)
            self._half_open_count += 1

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self.stats.successful_requests += 1
            self.stats.total_requests += 1
            self.stats.last_success_time = datetime.now(UTC)
            
            if self.state == CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                # Only close after enough consecutive successes
                if self._consecutive_successes >= self.config.min_throughput:
                    self.state = CircuitState.CLOSED
                    self.last_state_change = datetime.now(UTC)
                    logger.info(
                        f"Circuit {self.name} closed after successful recovery "
                        f"{self._consecutive_successes}/{self.config.min_throughput} successes"
                    )

    async def _on_failure(self, error: Exception, context: CircuitContext) -> None:
        """Handle failed call."""
        async with self._lock:
            self.stats.failed_requests += 1
            self.stats.total_requests += 1
            self.stats.last_failure_time = datetime.now(UTC)
            
            if self.state == CircuitState.CLOSED:
                failure_count = await self._get_recent_failures()
                
                if failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.last_state_change = datetime.now(UTC)
                    logger.warning(
                        f"Circuit {self.name} opened after {failure_count} failures. "
                        f"Last error: {str(error)}"
                    )
                    
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately opens circuit
                self.state = CircuitState.OPEN
                self.last_state_change = datetime.now(UTC)
                self._half_open_count = 0
                self._consecutive_successes = 0
                logger.warning(
                    f"Circuit {self.name} reopened after failed recovery attempt. "
                    f"Error: {str(error)}"
                )

    async def _get_recent_failures(self) -> int:
        """Get number of failures in recent window."""
        if not self.stats.last_failure_time:
            return 0

        now = datetime.now(UTC)
        window_start = now.timestamp() - self.config.failure_window
        
        if self.stats.last_failure_time.timestamp() < window_start:
            return 0
            
        return self.stats.failed_requests

    async def reset(self) -> None:
        """Reset circuit breaker state."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.stats = CircuitStats()
            self.last_state_change = datetime.now(UTC)
            self._half_open_count = 0
            self._consecutive_successes = 0
            logger.info(f"Circuit {self.name} reset to initial state")