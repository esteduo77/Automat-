"""Small in-process rate limiter and baseline response hardening.

Use a shared edge/API gateway limiter for multi-process or multi-instance production.
"""
from collections import defaultdict, deque
from time import monotonic
from fastapi import Request
from fastapi.responses import JSONResponse

_windows = defaultdict(deque)
_LIMITS = {
    "/api/auth/login": (10, 300),
    "/api/auth/register": (5, 3600),
}

async def security_middleware(request: Request, call_next):
    path = request.url.path
    now = monotonic()
    client = request.client.host if request.client else "unknown"
    limit, period = _LIMITS.get(path, (180, 60))
    key = f"{client}:{path if path in _LIMITS else 'api'}"
    bucket = _windows[key]
    while bucket and bucket[0] <= now - period:
        bucket.popleft()
    if path.startswith("/api/") and len(bucket) >= limit:
        return JSONResponse(status_code=429, content={"detail": "Trop de requêtes. Réessayez plus tard."},
                            headers={"Retry-After": str(max(1, int(period - (now - bucket[0]))))})
    if path.startswith("/api/"):
        bucket.append(now)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
