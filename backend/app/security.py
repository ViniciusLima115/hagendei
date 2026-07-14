import os
import secrets
import time
from uuid import uuid4

import jwt as pyjwt
from passlib.context import CryptContext
from pydantic import BaseModel

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(plain: str) -> str:
    return _pwd_context.hash(plain)


def verificar_senha(plain: str, hashed: str) -> bool:
    if not hashed or _pwd_context.identify(hashed) != "bcrypt":
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except (TypeError, ValueError):
        return False


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}


def _load_jwt_secret() -> str:
    configured = os.getenv("JWT_SECRET", "").strip()
    if configured:
        if len(configured.encode("utf-8")) < 32:
            raise RuntimeError("JWT_SECRET deve ter ao menos 32 bytes.")
        return configured
    if IS_PRODUCTION:
        raise RuntimeError("JWT_SECRET e obrigatorio em producao.")
    return secrets.token_urlsafe(48)


JWT_SECRET = _load_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = max(5, min(int(os.getenv("JWT_EXPIRES_MINUTES", "480")), 1440))
JWT_ISSUER = os.getenv("JWT_ISSUER", "hagendei-api").strip()
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "hagendei-web").strip()
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "hagendei_session").strip()
SESSION_COOKIE_SECURE = os.getenv(
    "SESSION_COOKIE_SECURE",
    "true" if IS_PRODUCTION else "false",
).strip().lower() in {"1", "true", "yes", "on"}


class TokenClaims(BaseModel):
    sub: str
    tenant_id: int | None = None
    is_admin: bool = False
    role: str | None = None
    jti: str
    iss: str
    aud: str
    session_version: int = 0
    iat: int
    exp: int


def create_access_token(
    sub: str,
    tenant_id: int | None,
    is_admin: bool,
    expires_minutes: int | None = None,
    role: str | None = None,
    session_version: int = 0,
) -> str:
    now = int(time.time())
    ttl = expires_minutes if expires_minutes is not None else JWT_EXPIRES_MINUTES
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "is_admin": is_admin,
        "role": role,
        "jti": str(uuid4()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "session_version": session_version,
        "iat": now,
        "exp": now + (ttl * 60),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenClaims:
    try:
        payload = pyjwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub", "jti", "iss", "aud", "session_version"]},
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise ValueError("Token expirado.") from exc
    except pyjwt.InvalidTokenError as exc:
        raise ValueError("Token invalido.") from exc
    return TokenClaims(**payload)


def bearer_token_exposed_in_response() -> bool:
    configured = os.getenv("AUTH_EXPOSE_BEARER_TOKEN")
    if configured is None:
        return not IS_PRODUCTION
    return configured.strip().lower() in {"1", "true", "yes", "on"}
