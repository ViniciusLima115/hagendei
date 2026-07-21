from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PlanoEstabelecimento = Literal["basico", "premium"]
StatusManualEstabelecimento = Literal["ativo", "inativo"]


class EstabelecimentoAdminCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    login: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9._@+-]+$")
    senha: str = Field(min_length=8, max_length=128)
    plano: PlanoEstabelecimento = "basico"
    status_manual: StatusManualEstabelecimento = "ativo"
    vencimento_em: date
    trial_ativo: bool = False
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    endereco: str = Field(default="", max_length=255)

    @field_validator("senha")
    @classmethod
    def validar_tamanho_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("A senha deve ter no maximo 72 bytes.")
        return value


class EstabelecimentoAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    login: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9._@+-]+$")
    senha: str = Field(min_length=8, max_length=128)
    plano: PlanoEstabelecimento
    status_manual: StatusManualEstabelecimento
    vencimento_em: date
    trial_ativo: bool
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    endereco: str = Field(default="", max_length=255)

    @field_validator("senha")
    @classmethod
    def validar_tamanho_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("A senha deve ter no maximo 72 bytes.")
        return value


class EstabelecimentoAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    slug: str | None = None
    login: str | None = None
    senha: str | None = Field(default=None, exclude=True)
    plano: PlanoEstabelecimento | None = "basico"
    status_manual: StatusManualEstabelecimento | None = "ativo"
    vencimento_em: date | None = None
    trial_ativo: bool = False
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    criado_em: datetime


class EstabelecimentoFuncionamentoDia(BaseModel):
    ativo: bool = True
    inicio: str = "08:00"
    fim: str = "18:00"

    @field_validator("inicio", "fim")
    @classmethod
    def validar_hora(cls, value: str) -> str:
        texto = value.strip()
        try:
            datetime.strptime(texto, "%H:%M")
        except ValueError as exc:
            raise ValueError("Horario deve estar no formato HH:MM.") from exc
        return texto


class EstabelecimentoFuncionamento(BaseModel):
    seg: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    ter: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    qua: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    qui: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    sex: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    sab: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    dom: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    intervalo_minutos: int | None = None  # 5–120, step 5

    @model_validator(mode="after")
    def validar_intervalos(self):
        for dia in ("seg", "ter", "qua", "qui", "sex", "sab", "dom"):
            item = getattr(self, dia)
            if item.ativo and item.inicio >= item.fim:
                raise ValueError(f"{dia}: horario inicial precisa ser menor que o final.")
        return self
