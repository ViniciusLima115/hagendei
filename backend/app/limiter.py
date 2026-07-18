import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
_IS_PRODUCTION = _APP_ENV in {"prod", "production"}
_AUTH_LIMIT_DEFAULT = "5/minute" if _IS_PRODUCTION else "30/minute"

RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", _AUTH_LIMIT_DEFAULT)
RATE_LIMIT_MFA = os.getenv("RATE_LIMIT_MFA", _AUTH_LIMIT_DEFAULT)
RATE_LIMIT_PUBLIC = os.getenv("RATE_LIMIT_PUBLIC", "30/minute")
RATE_LIMIT_PAYMENT_STATUS = os.getenv("RATE_LIMIT_PAYMENT_STATUS", "20/minute")
RATE_LIMIT_WEBHOOK = os.getenv("RATE_LIMIT_WEBHOOK", "120/minute")
RATE_LIMIT_STORAGE_URI = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://").strip() or "memory://"


def _get_real_ip(request) -> str:
    # ProxyHeadersMiddleware rewrites request.client only for explicitly trusted proxies.
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_real_ip,
    storage_uri=RATE_LIMIT_STORAGE_URI,
    key_prefix="hagendei",
    in_memory_fallback_enabled=False,
    swallow_errors=False,
)
