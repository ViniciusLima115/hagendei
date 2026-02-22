from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.agendamento import (
    AgendamentoCreate,
    AgendamentoResponse,
    AgendamentoUpdate,
    AgendamentoStatusUpdate,
)
from app.services.agendamento_service import (
    criar_agendamento,
    listar_agendamentos,
    atualizar_agendamento,
    atualizar_status_agendamento,
    remover_agendamento,
)

router = APIRouter(prefix="/agendamentos")


@router.post("/", response_model=AgendamentoResponse)
def criar(dados: AgendamentoCreate, db: Session = Depends(get_db)):
    try:
        return criar_agendamento(db, dados)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=list[AgendamentoResponse])
def listar(db: Session = Depends(get_db)):
    return listar_agendamentos(db)


@router.put("/{agendamento_id}", response_model=AgendamentoResponse)
def atualizar(
    agendamento_id: int,
    dados: AgendamentoUpdate,
    db: Session = Depends(get_db),
):
    try:
        return atualizar_agendamento(db, agendamento_id, dados)
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "não encontrado" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc


@router.patch("/{agendamento_id}/status", response_model=AgendamentoResponse)
def atualizar_status(
    agendamento_id: int,
    dados: AgendamentoStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        return atualizar_status_agendamento(db, agendamento_id, dados.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{agendamento_id}", status_code=204)
def remover(agendamento_id: int, db: Session = Depends(get_db)):
    try:
        remover_agendamento(db, agendamento_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
