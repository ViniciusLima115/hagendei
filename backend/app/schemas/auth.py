from pydantic import BaseModel


class AdminCheckRequest(BaseModel):
    usuario: str
    senha: str


class AdminCheckResponse(BaseModel):
    is_admin: bool


class LoginRequest(BaseModel):
    usuario: str
    senha: str


class LoginResponse(BaseModel):
    is_admin: bool
    tenant_id: int | None = None
    tenant_name: str | None = None
    plano: str | None = None
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: int | None = None
    nome: str
    plano: str
    is_admin: bool
    tipo_servico: str | None = None  # None para admin
