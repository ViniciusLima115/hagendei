from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate, ClienteResponse, ClienteUpdate

router = APIRouter(prefix="/clientes")


@router.post("/", response_model=ClienteResponse)
def criar(dados: ClienteCreate, db: Session = Depends(get_db)):
    cliente_existente = db.query(Cliente).filter(Cliente.telefone == dados.telefone).first()
    if cliente_existente:
        raise HTTPException(status_code=400, detail="Telefone já cadastrado")

    cliente = Cliente(**dados.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)

    return cliente


@router.get("/", response_model=list[ClienteResponse])
def listar(db: Session = Depends(get_db)):
    return db.query(Cliente).order_by(Cliente.id.asc()).all()


@router.put("/{cliente_id}", response_model=ClienteResponse)
def atualizar(cliente_id: int, dados: ClienteUpdate, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    conflito_telefone = (
        db.query(Cliente)
        .filter(Cliente.telefone == dados.telefone, Cliente.id != cliente_id)
        .first()
    )
    if conflito_telefone:
        raise HTTPException(status_code=400, detail="Telefone já cadastrado")

    cliente.nome = dados.nome
    cliente.telefone = dados.telefone
    if dados.etapa_atual is not None:
        cliente.etapa_atual = dados.etapa_atual
    db.commit()
    db.refresh(cliente)
    return cliente


@router.delete("/{cliente_id}", status_code=204)
def remover(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    db.delete(cliente)
    db.commit()
