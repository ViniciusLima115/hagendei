import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.estabelecimento import Estabelecimento
from app.routes.deps import require_admin
from app.security import TokenClaims, hash_senha
from app.services.admin_audit_service import create_admin_audit_log
from app.schemas.barbearia import (
    BarbeariaAdminCreate,
    BarbeariaAdminResponse,
    BarbeariaAdminUpdate,
)

router = APIRouter(prefix="/estabelecimentos", dependencies=[Depends(require_admin)])


def _audit_tenant_action(
    db: Session,
    request: Request,
    claims: TokenClaims,
    estabelecimento: Estabelecimento,
    action: str,
) -> None:
    create_admin_audit_log(
        db,
        admin_user_id=claims.sub,
        establishment_id=estabelecimento.id,
        action=action,
        entity_type="establishment",
        entity_id=estabelecimento.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={
            "result": "success",
            "correlation_id": request.headers.get("x-request-id"),
            "status": estabelecimento.status_manual,
            "plan": estabelecimento.plano,
        },
    )


def _slugify(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto.strip().lower()).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "estabelecimento"


def _gerar_slug_unico(db: Session, nome: str, slug_informado: str | None, *, excluir_id: int | None = None) -> str:
    base = _slugify(slug_informado or nome)
    slug = base
    idx = 2

    while True:
        query = db.query(Estabelecimento).filter(Estabelecimento.slug == slug)
        if excluir_id is not None:
            query = query.filter(Estabelecimento.id != excluir_id)
        conflito = query.first()
        if not conflito:
            return slug
        slug = f"{base}-{idx}"
        idx += 1


@router.get("/", response_model=list[BarbeariaAdminResponse])
def listar(db: Session = Depends(get_db)):
    return db.query(Estabelecimento).order_by(Estabelecimento.criado_em.desc(), Estabelecimento.id.desc()).all()


@router.post("/", response_model=BarbeariaAdminResponse)
def criar(
    dados: BarbeariaAdminCreate,
    request: Request,
    claims: TokenClaims = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slug = _gerar_slug_unico(db, dados.nome, dados.slug)
    login = dados.login.strip().lower()

    login_existente = db.query(Estabelecimento).filter(Estabelecimento.login == login).first()
    if login_existente:
        raise HTTPException(status_code=400, detail="Ja existe um estabelecimento com esse login.")

    estabelecimento = Estabelecimento(
        nome=dados.nome.strip(),
        slug=slug,
        login=login,
        senha=hash_senha(dados.senha),
        plano=dados.plano,
        status_manual=dados.status_manual,
        vencimento_em=dados.vencimento_em,
        trial_ativo=dados.trial_ativo,
        trial_fim_em=dados.trial_fim_em if dados.trial_ativo else None,
        ultimo_acesso_em=dados.ultimo_acesso_em,
        pagamento_recusado=dados.pagamento_recusado,
        endereco=dados.endereco.strip(),
    )
    db.add(estabelecimento)
    db.commit()
    db.refresh(estabelecimento)
    _audit_tenant_action(db, request, claims, estabelecimento, "tenant_account_created")
    return estabelecimento


@router.put("/{estabelecimento_id}", response_model=BarbeariaAdminResponse)
def atualizar(
    estabelecimento_id: int,
    dados: BarbeariaAdminUpdate,
    request: Request,
    claims: TokenClaims = Depends(require_admin),
    db: Session = Depends(get_db),
):
    estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.id == estabelecimento_id).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")

    slug = _gerar_slug_unico(db, dados.nome, dados.slug, excluir_id=estabelecimento_id)
    login = dados.login.strip().lower()

    conflito_login = (
        db.query(Estabelecimento)
        .filter(Estabelecimento.login == login, Estabelecimento.id != estabelecimento_id)
        .first()
    )
    if conflito_login:
        raise HTTPException(status_code=400, detail="Ja existe outro estabelecimento com esse login.")

    estabelecimento.nome = dados.nome.strip()
    estabelecimento.slug = slug
    estabelecimento.login = login
    estabelecimento.senha = hash_senha(dados.senha)
    estabelecimento.auth_version = int(estabelecimento.auth_version or 0) + 1
    estabelecimento.plano = dados.plano
    estabelecimento.status_manual = dados.status_manual
    estabelecimento.vencimento_em = dados.vencimento_em
    estabelecimento.trial_ativo = dados.trial_ativo
    estabelecimento.trial_fim_em = dados.trial_fim_em if dados.trial_ativo else None
    estabelecimento.ultimo_acesso_em = dados.ultimo_acesso_em
    estabelecimento.pagamento_recusado = dados.pagamento_recusado
    estabelecimento.endereco = dados.endereco.strip()
    db.commit()
    db.refresh(estabelecimento)
    _audit_tenant_action(db, request, claims, estabelecimento, "tenant_account_updated")
    return estabelecimento


@router.delete("/{estabelecimento_id}", status_code=204)
def remover(
    estabelecimento_id: int,
    request: Request,
    claims: TokenClaims = Depends(require_admin),
    db: Session = Depends(get_db),
):
    estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.id == estabelecimento_id).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")

    estabelecimento.status_manual = "inativo"
    estabelecimento.auth_version = int(estabelecimento.auth_version or 0) + 1
    _audit_tenant_action(db, request, claims, estabelecimento, "tenant_account_disabled")
