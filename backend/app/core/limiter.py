import os
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_real_client_ip(request):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Enabled in production/development, disabled during automated integration test runs
limiter = Limiter(
    key_func=get_real_client_ip,
    enabled=(os.getenv("TESTING") != "1"),
)
