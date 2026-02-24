import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.barbearia import Barbearia
from app.schemas.auth import AdminCheckRequest, AdminCheckResponse, LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_USUARIO = "vhtech_"
ADMIN_SENHA = "@dinizvascaino"


@router.post("/admin-check", response_model=AdminCheckResponse)
def admin_check(payload: AdminCheckRequest):
    is_admin_user = secrets.compare_digest(payload.usuario, ADMIN_USUARIO)
    is_admin_pass = secrets.compare_digest(payload.senha, ADMIN_SENHA)
    return AdminCheckResponse(is_admin=is_admin_user and is_admin_pass)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    usuario = payload.usuario.strip().lower()
    senha = payload.senha

    is_admin_user = secrets.compare_digest(usuario, ADMIN_USUARIO)
    is_admin_pass = secrets.compare_digest(senha, ADMIN_SENHA)
    if is_admin_user and is_admin_pass:
        return LoginResponse(
            is_admin=True,
            tenant_id=None,
            tenant_name="Administrador",
            plano="premium",
        )

    barbearia = db.query(Barbearia).filter(Barbearia.login == usuario).first()
    if not barbearia or not barbearia.senha:
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")

    if not secrets.compare_digest(barbearia.senha, senha):
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")

    return LoginResponse(
        is_admin=False,
        tenant_id=barbearia.id,
        tenant_name=barbearia.nome,
        plano=(barbearia.plano or "basico").lower(),
    )
