from pydantic import BaseModel

class BarbeiroCreate(BaseModel):
    nome: str


class BarbeiroUpdate(BaseModel):
    nome: str


class BarbeiroResponse(BaseModel):
    id: int
    nome: str
    barbearia_id: int


    class Config:
        from_attributes = True
