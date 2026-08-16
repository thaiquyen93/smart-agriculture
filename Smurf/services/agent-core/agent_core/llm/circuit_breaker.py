"""Circuit breaker for the LLM client (M4.5 fault tolerance).

Prevents cascading stalls when LM Studio or Gemini is unreachable.
After `failure_threshold` consecutive failures the circuit opens: all
subsequent `chat()` calls return immediately with `ok=False` and
`error_code=CIRCUIT_OPEN` instead of waiting up to `timeout_sec` per call.

The circuit moves through three states:
  CLOSED      — normal operation; failures are counted
  OPEN        — short-circuit; calls return instantly until `reset_sec`
  HALF_OPEN   — one probe call allowed after `reset_sec` to test recovery

This module has no network dependency — it is a pure state-machine and
can be instantiated and tested without any LLM provider reachable.
"""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Exported so structured_output.py can reference it as a named constant
# rather than a magic string.
CIRCUIT_OPEN = "CIRCUIT_OPEN"


class CircuitBreaker:
    """Thread-safe circuit breaker.

    Args:
        failure_threshold: Number of consecutive failures before the circuit
            opens.  Default 3.
        reset_sec: Seconds to wait in OPEN state before allowing one probe
            call (transition to HALF_OPEN).  Default 30.0.
        name: Used in log messages — set to the provider name for clarity.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        reset_sec: float = 30.0,
        name: str = "llm",
    ) -> None:
        self._threshold = failure_threshold
        self._reset_sec = reset_sec
        self._name = name

        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None  # monotonic timestamp when opened

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        """Current state string: ``"CLOSED"``, ``"OPEN"``, or ``"HALF_OPEN"``."""
        with self._lock:
            return self._state_unlocked()

    @property
    def is_open(self) -> bool:
        """``True`` when the circuit is open (calls should be short-circuited)."""
        with self._lock:
            return self._state_unlocked() == "OPEN"

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._failures

    def before_call(self) -> bool:
        """Call this before each LLM request.

        Returns:
            ``True`` if the call may proceed (circuit CLOSED or HALF_OPEN).
            ``False`` if the circuit is OPEN — caller should short-circuit.
        """
        with self._lock:
            state = self._state_unlocked()
            if state == "CLOSED":
                return True
            if state == "HALF_OPEN":
                # Allow exactly one probe; keep _opened_at so the window
                # resets if the probe also fails.
                logger.info("CircuitBreaker(%s): HALF_OPEN — allowing one probe call", self._name)
                return True
            # OPEN
            return False

    def record_success(self) -> None:
        """Record a successful LLM call; reset failure counter, close circuit."""
        with self._lock:
            if self._failures > 0 or self._opened_at is not None:
                logger.info(
                    "CircuitBreaker(%s): recovered after %d failure(s) — closing circuit",
                    self._name, self._failures,
                )
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        """Record a failed LLM call; open the circuit when threshold reached."""
        with self._lock:
            self._failures += 1
            state = self._state_unlocked()
            if state in ("CLOSED", "HALF_OPEN") and self._failures >= self._threshold:
                self._opened_at = time.monotonic()
                logger.warning(
                    "CircuitBreaker(%s): OPENING after %d consecutive failure(s)",
                    self._name, self._failures,
                )

    # ------------------------------------------------------------------
    # Internal helpers (must be called with _lock held)
    # ------------------------------------------------------------------

    def _state_unlocked(self) -> str:
        if self._opened_at is None:
            return "CLOSED"
        elapsed = time.monotonic() - self._opened_at
        if elapsed >= self._reset_sec:
            return "HALF_OPEN"
        return "OPEN"
