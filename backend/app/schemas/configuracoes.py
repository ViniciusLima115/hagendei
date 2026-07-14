import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class PerfilUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str | None = Field(default=None, min_length=2, max_length=255)
    endereco: str | None = Field(default=None, max_length=255)
    whatsapp_number: str | None = Field(default=None, max_length=30, pattern=r"^[0-9+().\s-]+$")
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SenhaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    senha_atual: str = Field(min_length=1, max_length=1024)
    nova_senha: str = Field(min_length=8, max_length=128)

    @field_validator("nova_senha")
    @classmethod
    def nova_senha_minima(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("A nova senha deve ter no maximo 72 bytes.")
        return v


class TemaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    accent_color: str | None = Field(default=None, max_length=7)
    bg_color: str | None = Field(default=None, max_length=7)
    logo_url: str | None = Field(default=None, max_length=500)

    @field_validator("accent_color", "bg_color")
    @classmethod
    def validar_hex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("Cor deve estar no formato hexadecimal #rrggbb.")
        return v

    @field_validator("logo_url")
    @classmethod
    def validar_logo_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.startswith("https://"):
            raise ValueError("logo_url deve começar com https://")
        return v


class NotificacoesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notif_ativo: bool | None = None
    notif_horas_antes: int | None = None

    @field_validator("notif_horas_antes")
    @classmethod
    def validar_horas(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if v not in [1, 2, 4, 8, 24]:
            raise ValueError("notif_horas_antes deve ser um de: 1, 2, 4, 8, 24.")
        return v
