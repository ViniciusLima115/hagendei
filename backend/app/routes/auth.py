import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import RATE_LIMIT_LOGIN, limiter
from app.models.estabelecimento import Estabelecimento
from app.models.token_blacklist import TokenBlacklist
from app.routes.deps import get_current_claims, tenant_account_is_active
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.security import (
    JWT_EXPIRES_MINUTES,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE,
    TokenClaims,
    bearer_token_exposed_in_response,
    create_access_token,
    hash_senha,
    verificar_senha,
)

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_USUARIO = os.getenv("ADMIN_USUARIO", "").strip().lower()
ADMIN_SENHA = os.getenv("ADMIN_SENHA", "")
_DUMMY_PASSWORD_HASH = hash_senha(secrets.token_urlsafe(32))


def _find_establishment_for_login(db: Session, usuario: str) -> Estabelecimento | None:
    exact = db.query(Estabelecimento).filter(func.lower(Estabelecimento.login) == usuario).first()
    if exact or "@" in usuario:
        return exact

    escaped = usuario.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    matches = (
        db.query(Estabelecimento)
        .filter(func.lower(Estabelecimento.login).like(f"{escaped}@%", escape="\\"))
        .limit(2)
        .all()
    )
    return matches[0] if len(matches) == 1 else None


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=JWT_EXPIRES_MINUTES * 60,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit(RATE_LIMIT_LOGIN)
def login(request: Request, response: Response, payload: LoginRequest, db: Session = Depends(get_db)):
    usuario = payload.usuario.strip().lower()
    senha = payload.senha

    is_admin_user = bool(ADMIN_USUARIO) and secrets.compare_digest(usuario, ADMIN_USUARIO)
    is_admin_pass = bool(ADMIN_SENHA) and secrets.compare_digest(senha, ADMIN_SENHA)
    if is_admin_user and is_admin_pass:
        token = create_access_token(sub=usuario, tenant_id=None, is_admin=True)
        _set_session_cookie(response, token)
        return LoginResponse(
            is_admin=True,
            tenant_id=None,
            tenant_name="Administrador",
            plano="premium",
            access_token=token if bearer_token_exposed_in_response() else None,
            token_type="bearer",
        )

    estabelecimento = _find_establishment_for_login(db, usuario)
    stored_hash = estabelecimento.senha if estabelecimento and estabelecimento.senha else _DUMMY_PASSWORD_HASH
    password_valid = verificar_senha(senha, stored_hash)
    if not estabelecimento or not password_valid:
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")
    if not tenant_account_is_active(estabelecimento):
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")

    token = create_access_token(
        sub=usuario,
        tenant_id=estabelecimento.id,
        is_admin=False,
        session_version=int(estabelecimento.auth_version or 0),
    )
    _set_session_cookie(response, token)
    return LoginResponse(
        is_admin=False,
        tenant_id=estabelecimento.id,
        tenant_name=estabelecimento.nome,
        plano=(estabelecimento.plano or "basico").lower(),
        access_token=token if bearer_token_exposed_in_response() else None,
        token_type="bearer",
    )


@router.get("/me", response_model=MeResponse)
def me(
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    if claims.is_admin:
        return MeResponse(nome="Administrador", plano="premium", is_admin=True)

    estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.id == claims.tenant_id).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")

    return MeResponse(
        id=estabelecimento.id,
        nome=estabelecimento.nome,
        plano=(estabelecimento.plano or "basico").lower(),
        is_admin=False,
        tipo_servico=getattr(estabelecimento, "tipo_servico", "geral") or "geral",
        accent_color=estabelecimento.accent_color or "#d4930a",
        bg_color=estabelecimento.bg_color or "#ffffff",
        logo_url=estabelecimento.logo_url,
        notif_ativo=estabelecimento.notif_ativo if estabelecimento.notif_ativo is not None else True,
        notif_horas_antes=(
            estabelecimento.notif_horas_antes if estabelecimento.notif_horas_antes is not None else 2
        ),
    )


@router.post("/logout", status_code=200)
def logout(
    response: Response,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    expires_at = datetime.fromtimestamp(claims.exp, tz=timezone.utc).replace(tzinfo=None)
    db.merge(TokenBlacklist(jti=claims.jti, expires_at=expires_at))
    db.commit()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    return {"detail": "Logout realizado com sucesso."}
