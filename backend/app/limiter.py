import os
from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
RATE_LIMIT_PUBLIC = os.getenv("RATE_LIMIT_PUBLIC", "30/minute")

limiter = Limiter(key_func=get_remote_address)
