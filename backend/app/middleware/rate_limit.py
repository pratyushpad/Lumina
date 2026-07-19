"""slowapi rate limiter (in-memory, per-client-IP).

Behind a reverse proxy (HF Spaces, most PaaS) the socket peer address is an
internal mesh IP that varies per request, which fragments per-IP buckets and
silently disables limiting. Key on the first X-Forwarded-For hop when present
(always set by the platform proxy in prod); fall back to the socket address
for direct/local access.
"""
from starlette.requests import Request

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_ip,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)
