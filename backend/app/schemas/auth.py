from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: str = Field(min_length=1, max_length=255)
    senha: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    is_admin: bool
    tenant_id: int | None = None
    tenant_name: str | None = None
    plano: str | None = None
    access_token: str | None = None
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: int | None = None
    nome: str
    plano: str
    is_admin: bool
    tipo_servico: str | None = None  # None para admin
    # Tema por tenant (admin retorna defaults)
    accent_color: str = "#d4930a"
    bg_color: str = "#ffffff"
    logo_url: str | None = None
    notif_ativo: bool = True
    notif_horas_antes: int = 2
