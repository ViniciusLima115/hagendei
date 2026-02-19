from sqlalchemy import Column, Integer, String
from app.database import Base


class Barbearia(Base):
    __tablename__ = "barbearias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    endereco = Column(String(255), nullable=False)
