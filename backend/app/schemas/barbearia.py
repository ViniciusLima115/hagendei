from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PlanoBarbearia = Literal["basico", "premium"]
StatusManualBarbearia = Literal["ativo", "inativo"]


class BarbeariaAdminCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    login: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9._@+-]+$")
    senha: str = Field(min_length=8, max_length=128)
    plano: PlanoBarbearia = "basico"
    status_manual: StatusManualBarbearia = "ativo"
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


class BarbeariaAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    login: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9._@+-]+$")
    senha: str = Field(min_length=8, max_length=128)
    plano: PlanoBarbearia
    status_manual: StatusManualBarbearia
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


class BarbeariaAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    slug: str | None = None
    login: str | None = None
    senha: str | None = Field(default=None, exclude=True)
    plano: PlanoBarbearia | None = "basico"
    status_manual: StatusManualBarbearia | None = "ativo"
    vencimento_em: date | None = None
    trial_ativo: bool = False
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    criado_em: datetime


class BarbeariaFuncionamentoDia(BaseModel):
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


class BarbeariaFuncionamento(BaseModel):
    seg: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    ter: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    qua: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    qui: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    sex: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    sab: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    dom: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    intervalo_minutos: int | None = None  # 5–120, step 5

    @model_validator(mode="after")
    def validar_intervalos(self):
        for dia in ("seg", "ter", "qua", "qui", "sex", "sab", "dom"):
            item = getattr(self, dia)
            if item.ativo and item.inicio >= item.fim:
                raise ValueError(f"{dia}: horario inicial precisa ser menor que o final.")
        return self


# Aliases de compatibilidade — usar os novos nomes em código novo
EstabelecimentoAdminCreate = BarbeariaAdminCreate
EstabelecimentoAdminUpdate = BarbeariaAdminUpdate
EstabelecimentoAdminResponse = BarbeariaAdminResponse
EstabelecimentoFuncionamentoDia = BarbeariaFuncionamentoDia
EstabelecimentoFuncionamento = BarbeariaFuncionamento
