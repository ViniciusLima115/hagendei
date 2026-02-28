from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.public import (
    PublicAgendamentoCreate,
    PublicAgendamentoResponse,
    PublicBarbeiroItem,
    PublicBarbeariaLookupResponse,
    PublicServicoItem,
)
from app.services.public_booking_service import (
    criar_agendamento_publico,
    listar_barbeiros_publico,
    listar_horarios_disponiveis_publico,
    listar_servicos_publico,
    obter_lookup_publico,
    obter_lookup_publico_por_id,
)


router = APIRouter(prefix="/public", tags=["public"])


@router.get("/barbearia/{slug}", response_model=PublicBarbeariaLookupResponse)
def lookup_barbearia_publica(
    slug: str,
    data: date | None = Query(default=None),
    barbeiro_id: int | None = Query(default=None),
    servico_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return obter_lookup_publico(
            db,
            slug=slug,
            data_referencia=data,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/barbearia-id/{barbearia_id}", response_model=PublicBarbeariaLookupResponse)
def lookup_barbearia_publica_por_id(
    barbearia_id: int,
    data: date | None = Query(default=None),
    barbeiro_id: int | None = Query(default=None),
    servico_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return obter_lookup_publico_por_id(
            db,
            barbearia_id=barbearia_id,
            data_referencia=data,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/servicos", response_model=list[PublicServicoItem])
def listar_servicos_public(
    barbearia_id: int = Query(...),
    db: Session = Depends(get_db),
):
    return listar_servicos_publico(db, barbearia_id=barbearia_id)


@router.get("/barbeiros", response_model=list[PublicBarbeiroItem])
def listar_barbeiros_public(
    barbearia_id: int = Query(...),
    db: Session = Depends(get_db),
):
    return listar_barbeiros_publico(db, barbearia_id=barbearia_id)


@router.get("/horarios-disponiveis")
def horarios_disponiveis_public(
    barbearia_id: int = Query(...),
    barbeiro_id: int = Query(...),
    servico_id: int = Query(...),
    data: date = Query(...),
    db: Session = Depends(get_db),
):
    return listar_horarios_disponiveis_publico(
        db,
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro_id,
        servico_id=servico_id,
        data_referencia=data,
    )


@router.post("/agendamentos", response_model=PublicAgendamentoResponse)
def criar_agendamento_public(
    dados: PublicAgendamentoCreate,
    db: Session = Depends(get_db),
):
    try:
        return criar_agendamento_publico(
            db,
            slug=dados.slug,
            barbearia_id=dados.barbearia_id,
            cliente_nome=dados.cliente_nome,
            cliente_telefone=dados.cliente_telefone,
            barbeiro_id=dados.barbeiro_id,
            servico_id=dados.servico_id,
            data=dados.data,
            hora_inicio=dados.hora_inicio,
        )
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "nao encontrada" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc
