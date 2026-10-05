import time
from enum import Enum
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.state = CircuitBreakerState.CLOSED
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info("Circuit Breaker transitioned to HALF_OPEN")
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise Exception("Circuit Breaker is OPEN. Fast failing.")

        try:
            result = func(*args, **kwargs)
            self._reset()
            return result
        except Exception as e:
            self._record_failure()
            raise e

    def _record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.warning(f"Circuit Breaker failure recorded. Count: {self.failure_count}")
        if self.failure_count >= self.failure_threshold:
            logger.error("Circuit Breaker transitioned to OPEN")
            self.state = CircuitBreakerState.OPEN

    def _reset(self):
        if self.state != CircuitBreakerState.CLOSED:
            logger.info("Circuit Breaker transitioned to CLOSED")
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
