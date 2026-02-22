from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.servico import Servico
from app.schemas.servico import ServicoCreate, ServicoResponse, ServicoUpdate

router = APIRouter(prefix="/servicos")


@router.post("/", response_model=ServicoResponse)
def criar(dados: ServicoCreate, db: Session = Depends(get_db)):
    servico = Servico(**dados.model_dump())

    db.add(servico)
    db.commit()
    db.refresh(servico)

    return servico


@router.get("/", response_model=list[ServicoResponse])
def listar(db: Session = Depends(get_db)):
    return db.query(Servico).all()


@router.put("/{servico_id}", response_model=ServicoResponse)
def atualizar(servico_id: int, dados: ServicoUpdate, db: Session = Depends(get_db)):
    servico = db.query(Servico).filter(Servico.id == servico_id).first()
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    servico.nome = dados.nome
    servico.duracao_minutos = dados.duracao_minutos
    servico.preco = dados.preco
    db.commit()
    db.refresh(servico)
    return servico


@router.delete("/{servico_id}", status_code=204)
def remover(servico_id: int, db: Session = Depends(get_db)):
    servico = db.query(Servico).filter(Servico.id == servico_id).first()
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    db.delete(servico)
    db.commit()
