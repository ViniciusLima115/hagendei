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
