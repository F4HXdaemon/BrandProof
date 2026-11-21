import time
from collections import defaultdict
from threading import Lock
from typing import Optional
from fastapi import Request, HTTPException, status


class SimpleRateLimiter:
    """
    Lightweight, thread-safe in-memory rate limiter using sliding timestamp windows.
    Protects sensitive operations like invitation validation and membership joins
    against brute-force enumeration without adding external dependencies.
    """

    def __init__(self, requests_per_minute: int = 20, window_seconds: float = 60.0):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.lock = Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self.lock:
            timestamps = self.requests[key]
            # Prune timestamps outside current window
            valid_timestamps = [t for t in timestamps if now - t < self.window_seconds]
            if len(valid_timestamps) >= self.requests_per_minute:
                self.requests[key] = valid_timestamps
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please wait a minute before trying again.",
                    headers={"Retry-After": str(int(self.window_seconds))},
                )
            valid_timestamps.append(now)
            self.requests[key] = valid_timestamps

    def reset_for_test(self) -> None:
        with self.lock:
            self.requests.clear()


# Global rate limiter instances
invite_validate_limiter = SimpleRateLimiter(requests_per_minute=30, window_seconds=60.0)
invite_join_limiter = SimpleRateLimiter(requests_per_minute=20, window_seconds=60.0)


def get_client_identifier(request: Request, user_id: Optional[str] = None) -> str:
    """Extract a unique client identifier from request and optional authenticated user id."""
    ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    if user_id:
        return f"{user_id}:{ip}"
    return ip
