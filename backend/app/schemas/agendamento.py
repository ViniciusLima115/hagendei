from typing import Literal

from pydantic import BaseModel
from datetime import datetime


StatusAgendamento = Literal["pendente", "confirmado", "cancelado", "reagendamento_solicitado"]


class AgendamentoCreate(BaseModel):
    telefone: str
    nome_cliente: str
    cliente_email: str | None = None
    barbeiro_id: int
    servico_id: int
    data_hora_inicio: datetime
    status: StatusAgendamento = "pendente"


class AgendamentoStatusUpdate(BaseModel):
    status: StatusAgendamento


class AgendamentoPatch(BaseModel):
    barbeiro_id: int | None = None
    servico_id: int | None = None
    data_hora_inicio: datetime | None = None
    cliente_email: str | None = None
    status: StatusAgendamento | None = None


class AgendamentoUpdate(BaseModel):
    barbeiro_id: int
    servico_id: int
    data_hora_inicio: datetime
    cliente_email: str | None = None
    status: StatusAgendamento = "confirmado"


class AgendamentoResponse(BaseModel):
    id: int

    cliente_nome: str
    telefone: str
    cliente_email: str | None = None

    barbeiro_nome: str
    servico_nome: str

    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: StatusAgendamento

    class Config:
        from_attributes = True


class AgendamentoRemarcacaoRequest(BaseModel):
    data_hora_inicio: datetime


class AgendamentoTokenDataResponse(BaseModel):
    id: int
    barbearia_id: int
    slug: str | None = None
    confirmation_token: str
    cliente_nome: str
    cliente_email: str | None = None
    barbeiro_id: int
    barbeiro_nome: str
    servico_id: int
    servico_nome: str
    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: StatusAgendamento
