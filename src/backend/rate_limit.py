"""Spec 146 — In-memory fixed-window rate limiter.

Provides:
- FixedWindowRateLimiter — thread-safe per-key counter.
- make_rate_limit_key() — builds a key from auth context + route group.
- require_rate_limit() — FastAPI dependency factory.
- BackendRateLimitError — raised when a request exceeds its limit.
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any

from fastapi import Request


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class FixedWindowRateLimiter:
    """Thread-safe fixed-window rate limiter.

    Each key gets its own counter that resets after window_seconds. A fresh
    instance is created per app so tests are completely isolated.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        # key → (count, window_start_epoch)
        self._windows: dict[str, tuple[int, float]] = {}

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """Check whether a request should be allowed.

        Returns (allowed, remaining, retry_after_seconds).
        """
        now = time.time()
        with self._lock:
            count, window_start = self._windows.get(key, (0, now))
            # Reset if the window has expired
            if now - window_start >= window_seconds:
                count = 0
                window_start = now
            if count >= limit:
                retry_after = max(1, int(window_seconds - (now - window_start)) + 1)
                return False, 0, retry_after
            count += 1
            self._windows[key] = (count, window_start)
            return True, limit - count, 0

    def reset(self, key: str | None = None) -> None:
        """Clear one key or all keys (useful in tests)."""
        with self._lock:
            if key is None:
                self._windows.clear()
            else:
                self._windows.pop(key, None)


# ---------------------------------------------------------------------------
# Rate limit key builder
# ---------------------------------------------------------------------------

def make_rate_limit_key(request: Request, route_group: str) -> str:
    """Build a rate-limit key that never includes raw tokens."""
    auth_ctx = getattr(request.state, "backend_auth_context", None)
    if auth_ctx is not None and getattr(auth_ctx, "ok", False):
        token_name = getattr(auth_ctx, "token_name", "") or "unknown"
        role = getattr(auth_ctx, "role", "") or "unknown"
        return f"{token_name}:{role}:{route_group}"
    # Unauthenticated — use client host
    client_host = _client_host(request)
    return f"anon:{client_host}:{route_group}"


def make_auth_failure_key(request: Request) -> str:
    client_host = _client_host(request)
    return f"anon:{client_host}:auth_failure"


def _client_host(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


# ---------------------------------------------------------------------------
# Exception for rate-limited requests
# ---------------------------------------------------------------------------

class BackendRateLimitError(Exception):
    def __init__(self, route_group: str, limit: int, retry_after: int) -> None:
        super().__init__(f"Rate limit exceeded for {route_group}")
        self.route_group = route_group
        self.limit = limit
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------

def require_rate_limit(route_group: str):
    """Return a FastAPI dependency that enforces the named rate limit group."""

    async def _check(request: Request) -> None:
        hardening = getattr(request.app.state, "backend_hardening_config", None)
        rate_limiter: FixedWindowRateLimiter | None = getattr(request.app.state, "rate_limiter", None)
        if hardening is None or not hardening.enabled or rate_limiter is None:
            return
        rl = hardening.rate_limits.get(route_group)
        if rl is None:
            return
        key = make_rate_limit_key(request, route_group)
        allowed, _remaining, retry_after = rate_limiter.check(key, rl.requests, rl.window_seconds)
        if not allowed:
            raise BackendRateLimitError(
                route_group=route_group,
                limit=rl.requests,
                retry_after=retry_after,
            )

    return _check
