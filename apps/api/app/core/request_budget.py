from collections import defaultdict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException


_requests: dict[tuple[str, int], deque[float]] = defaultdict(deque)
_lock = Lock()


def enforce_request_budget(
    bucket: str, limit: int, window_seconds: int = 3600
) -> None:
    with _lock:
        now = monotonic()
        requests = _requests[bucket, limit]
        while requests and now - requests[0] >= window_seconds:
            requests.popleft()
        if len(requests) >= limit:
            retry_after = max(1, ceil(window_seconds - (now - requests[0])))
            raise HTTPException(
                status_code=429,
                detail="RATE_LIMITED",
                headers={"Retry-After": str(retry_after)},
            )
        requests.append(now)
