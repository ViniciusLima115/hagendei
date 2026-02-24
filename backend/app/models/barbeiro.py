from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Barbeiro(Base):
    __tablename__ = "barbeiros"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=False, index=True)

    barbearia = relationship("Barbearia", back_populates="barbeiros")
