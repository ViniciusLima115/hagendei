import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import RATE_LIMIT_LOGIN, RATE_LIMIT_MFA, limiter
from app.models.admin_mfa import AdminMfaSetting
from app.models.estabelecimento import Estabelecimento
from app.models.token_blacklist import TokenBlacklist
from app.routes.deps import MFA_SETUP_ROLE, get_current_claims, require_admin_mfa_setup, require_recent_admin, tenant_account_is_active
from app.schemas.auth import (
    AdminMfaDisableRequest,
    AdminMfaSetupConfirmRequest,
    AdminMfaSetupConfirmResponse,
    AdminMfaSetupRequest,
    AdminMfaSetupResponse,
    AdminMfaStatusResponse,
    AdminMfaVerifyRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
)
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
from app.services.admin_audit_service import create_admin_audit_log
from app.services.admin_mfa_service import (
    consume_login_challenge,
    create_login_challenge,
    create_setup_payload,
    disable_mfa,
    enable_mfa,
    get_login_challenge_username,
    get_or_create_setting,
    verify_active_factor,
)

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_USUARIO = os.getenv("ADMIN_USUARIO", "").strip().lower()
ADMIN_SENHA = os.getenv("ADMIN_SENHA", "")
ADMIN_SENHA_HASH = os.getenv("ADMIN_SENHA_HASH", "").strip()
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


def _configured_admin_username() -> str:
    return ADMIN_USUARIO.strip().lower()


def _verify_admin_password(password: str) -> bool:
    if ADMIN_SENHA_HASH:
        return verificar_senha(password, ADMIN_SENHA_HASH)
    return bool(ADMIN_SENHA) and secrets.compare_digest(password, ADMIN_SENHA)


def _require_configured_admin(claims: TokenClaims) -> str:
    username = _configured_admin_username()
    can_manage_mfa = claims.is_admin or (claims.role or "").lower() == MFA_SETUP_ROLE
    if not username or not can_manage_mfa or not secrets.compare_digest(claims.sub.strip().lower(), username):
        raise HTTPException(status_code=403, detail="Acesso restrito ao superadmin.")
    return username


def _admin_login_response(response: Response, username: str, setting: AdminMfaSetting) -> LoginResponse:
    token = create_access_token(
        sub=username,
        tenant_id=None,
        is_admin=True,
        session_version=int(setting.session_version or 0),
    )
    _set_session_cookie(response, token)
    return LoginResponse(
        is_admin=True,
        tenant_id=None,
        tenant_name="Administrador",
        plano="premium",
        access_token=token if bearer_token_exposed_in_response() else None,
        token_type="bearer",
    )


def _mfa_setup_login_response(response: Response, username: str, setting: AdminMfaSetting) -> LoginResponse:
    token = create_access_token(
        sub=username,
        tenant_id=None,
        is_admin=False,
        role=MFA_SETUP_ROLE,
        session_version=int(setting.session_version or 0),
        expires_minutes=15,
    )
    _set_session_cookie(response, token)
    return LoginResponse(
        is_admin=True,
        tenant_id=None,
        tenant_name="Administrador",
        plano="premium",
        access_token=token if bearer_token_exposed_in_response() else None,
        token_type="bearer",
        mfa_setup_required=True,
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit(RATE_LIMIT_LOGIN)
def login(request: Request, response: Response, payload: LoginRequest, db: Session = Depends(get_db)):
    usuario = payload.usuario.strip().lower()
    senha = payload.senha

    is_admin_user = bool(ADMIN_USUARIO) and secrets.compare_digest(usuario, ADMIN_USUARIO)
    is_admin_pass = _verify_admin_password(senha)
    if is_admin_user and is_admin_pass:
        setting = get_or_create_setting(db, usuario)
        if setting.enabled:
            return LoginResponse(
                is_admin=True,
                mfa_required=True,
                mfa_challenge=create_login_challenge(db, usuario),
            )
        return _mfa_setup_login_response(response, usuario, setting)

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


@router.post("/admin/mfa/verify", response_model=LoginResponse)
@limiter.limit(RATE_LIMIT_MFA)
def verify_admin_mfa(request: Request, response: Response, payload: AdminMfaVerifyRequest, db: Session = Depends(get_db)):
    # The opaque challenge is issued only after the admin password was accepted.
    username = get_login_challenge_username(db, payload.challenge)
    if not username or not ADMIN_USUARIO or not secrets.compare_digest(username, _configured_admin_username()):
        raise HTTPException(status_code=401, detail="Codigo de verificacao invalido.")
    setting = db.get(AdminMfaSetting, username)
    if not setting or not setting.enabled:
        raise HTTPException(status_code=401, detail="Codigo de verificacao invalido.")
    verified, used_recovery_code = verify_active_factor(setting, payload.code)
    if not verified or not consume_login_challenge(db, setting.admin_username, payload.challenge):
        raise HTTPException(status_code=401, detail="Codigo de verificacao invalido.")
    action = "admin_mfa_recovery_code_used" if used_recovery_code else "admin_mfa_login_verified"
    create_admin_audit_log(
        db,
        admin_user_id=setting.admin_username,
        establishment_id=None,
        action=action,
        entity_type="admin_mfa",
        entity_id=setting.admin_username,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return _admin_login_response(response, setting.admin_username, setting)


@router.get("/admin/mfa/status", response_model=AdminMfaStatusResponse)
def admin_mfa_status(claims: TokenClaims = Depends(get_current_claims), db: Session = Depends(get_db)):
    username = _require_configured_admin(claims)
    setting = get_or_create_setting(db, username)
    return AdminMfaStatusResponse(
        enabled=bool(setting.enabled),
        recovery_codes_remaining=len(setting.recovery_code_hashes or []) if setting.enabled else 0,
    )


@router.post("/admin/mfa/setup", response_model=AdminMfaSetupResponse)
def admin_mfa_setup(
    payload: AdminMfaSetupRequest,
    claims: TokenClaims = Depends(require_admin_mfa_setup),
    db: Session = Depends(get_db),
):
    username = _require_configured_admin(claims)
    if not _verify_admin_password(payload.senha):
        raise HTTPException(status_code=401, detail="Senha atual invalida.")
    try:
        return AdminMfaSetupResponse(**create_setup_payload(db, username))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/admin/mfa/setup/confirm", response_model=AdminMfaSetupConfirmResponse)
def confirm_admin_mfa_setup(
    request: Request,
    response: Response,
    payload: AdminMfaSetupConfirmRequest,
    claims: TokenClaims = Depends(require_admin_mfa_setup),
    db: Session = Depends(get_db),
):
    username = _require_configured_admin(claims)
    try:
        recovery_codes = enable_mfa(db, username, payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    setting = get_or_create_setting(db, username)
    create_admin_audit_log(
        db,
        admin_user_id=username,
        establishment_id=None,
        action="admin_mfa_enabled",
        entity_type="admin_mfa",
        entity_id=username,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _admin_login_response(response, username, setting)
    return AdminMfaSetupConfirmResponse(recovery_codes=recovery_codes)


@router.post("/admin/mfa/disable", status_code=204)
def admin_mfa_disable(
    request: Request,
    response: Response,
    payload: AdminMfaDisableRequest,
    claims: TokenClaims = Depends(require_recent_admin),
    db: Session = Depends(get_db),
):
    username = _require_configured_admin(claims)
    setting = get_or_create_setting(db, username)
    verified, _ = verify_active_factor(setting, payload.code)
    if not setting.enabled or not _verify_admin_password(payload.senha) or not verified:
        raise HTTPException(status_code=401, detail="Senha ou codigo de verificacao invalido.")
    disable_mfa(db, username)
    create_admin_audit_log(
        db,
        admin_user_id=username,
        establishment_id=None,
        action="admin_mfa_disabled",
        entity_type="admin_mfa",
        entity_id=username,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _mfa_setup_login_response(response, username, get_or_create_setting(db, username))
    response.status_code = 204
    return None


@router.get("/me", response_model=MeResponse)
def me(
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    if claims.is_admin or (claims.role or "").lower() == MFA_SETUP_ROLE:
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
