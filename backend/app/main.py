import os
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.database import init_db
from app.limiter import limiter
from app.routes import (
    agenda,
    agendamentos,
    auth,
    chatbot,
    clientes,
    configuracoes,
    dashboard,
    estabelecimento_funcionamento,
    estabelecimentos,
    integrations,
    internal,
    notificacoes,
    payments,
    profissionais,
    public,
    servicos,
    webhook,
    webhooks,
    whatsapp,
)
from app.services.scheduler import start_scheduler, stop_scheduler

security = HTTPBasic()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def _is_production() -> bool:
    return os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}


def _validate_runtime_config() -> None:
    if not _is_production():
        return
    required = [
        "DATABASE_URL",
        "JWT_SECRET",
        "ENCRYPTION_KEY",
        "PAYMENT_CREDENTIALS_PEPPER",
        "ADMIN_USUARIO",
        "ADMIN_SENHA_HASH",
        "ALLOWED_HOSTS",
        "CORS_ALLOWED_ORIGINS",
        "TRUSTED_PROXY_IPS",
        "RATE_LIMIT_STORAGE_URI",
        "INTERNAL_REMINDER_TOKEN",
        "WHATSAPP_VERIFY_TOKEN",
        "WHATSAPP_APP_SECRET",
        "FRONTEND_URL",
        "BACKEND_PUBLIC_BASE_URL",
        "BOOKING_PUBLIC_BASE_URL",
    ]
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(f"Configuracao de producao incompleta: {', '.join(missing)}")
    if not os.getenv("RATE_LIMIT_STORAGE_URI", "").strip().lower().startswith(("redis://", "rediss://")):
        raise RuntimeError("RATE_LIMIT_STORAGE_URI deve usar Redis em producao.")
    admin_password_hash = os.getenv("ADMIN_SENHA_HASH", "").strip()
    if len(admin_password_hash) != 60 or not admin_password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        raise RuntimeError("ADMIN_SENHA_HASH deve conter um hash bcrypt valido em producao.")
    if _as_bool(os.getenv("AUTH_EXPOSE_BEARER_TOKEN"), False):
        raise RuntimeError("AUTH_EXPOSE_BEARER_TOKEN deve permanecer desativado em producao.")
    if not _as_bool(os.getenv("SESSION_COOKIE_SECURE"), True):
        raise RuntimeError("SESSION_COOKIE_SECURE deve permanecer ativo em producao.")
    if _as_bool(os.getenv("WHATSAPP_ALLOW_UNSIGNED_WEBHOOKS")) or _as_bool(
        os.getenv("MEGAAPI_WEBHOOK_ALLOW_UNSIGNED")
    ):
        raise RuntimeError("Webhooks sem assinatura nao podem ser habilitados em producao.")
    for origin in _csv_env("CORS_ALLOWED_ORIGINS"):
        if urlsplit(origin).scheme != "https":
            raise RuntimeError("CORS_ALLOWED_ORIGINS deve conter apenas origens HTTPS em producao.")
    for name in ("FRONTEND_URL", "BACKEND_PUBLIC_BASE_URL", "BOOKING_PUBLIC_BASE_URL"):
        if urlsplit(os.getenv(name, "")).scheme != "https":
            raise RuntimeError(f"{name} deve usar HTTPS em producao.")
    if _as_bool(os.getenv("DOCS_ENABLED")):
        if not os.getenv("DOCS_USER", "").strip() or len(os.getenv("DOCS_PASS", "")) < 14:
            raise RuntimeError("Documentacao habilitada exige DOCS_USER e DOCS_PASS forte.")


def _cors_origins() -> list[str]:
    configured = _csv_env("CORS_ALLOWED_ORIGINS")
    if _is_production():
        return configured
    return list(dict.fromkeys([
        *configured,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]))


def _cors_origin_regex() -> str | None:
    if _is_production() or not _as_bool(os.getenv("CORS_ALLOW_PRIVATE_NETWORKS"), True):
        return None
    return (
        r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?$"
    )


def _get_cors_allow_origin_regex() -> str | None:
    return _cors_origin_regex()


def verify_docs(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    expected_user = os.getenv("DOCS_USER", "")
    expected_password = os.getenv("DOCS_PASS", "")
    if not (
        expected_user
        and expected_password
        and secrets.compare_digest(credentials.username, expected_user)
        and secrets.compare_digest(credentials.password, expected_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_runtime_config()
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

trusted_proxies = _csv_env("TRUSTED_PROXY_IPS") or ["127.0.0.1"]
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted_proxies)
allowed_hosts = _csv_env("ALLOWED_HOSTS") or ["localhost", "127.0.0.1", "testserver"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Barbearia-Id", "X-Internal-Token"],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if _is_production():
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


if _as_bool(os.getenv("DOCS_ENABLED"), default=not _is_production()):
    @app.get("/docs", response_class=HTMLResponse)
    def custom_swagger_ui(_: None = Depends(verify_docs)):
        return get_swagger_ui_html(openapi_url="/openapi.json", title="Hagendei API")

    @app.get("/openapi.json")
    def openapi(_: None = Depends(verify_docs)):
        return app.openapi()


app.include_router(agendamentos.router)
app.include_router(clientes.router)
app.include_router(servicos.router)
app.include_router(agenda.router)
app.include_router(dashboard.router)
app.include_router(chatbot.router)
app.include_router(whatsapp.router, prefix="/whatsapp")
app.include_router(webhooks.router)
app.include_router(webhook.router)
app.include_router(public.router)
app.include_router(internal.router)
app.include_router(auth.router)
app.include_router(estabelecimentos.router)
app.include_router(profissionais.router)
app.include_router(estabelecimento_funcionamento.router)
app.include_router(configuracoes.router)
app.include_router(notificacoes.router)
app.include_router(integrations.router)
app.include_router(payments.router)


@app.get("/")
def home():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "hagendei-api"}
