from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import (
        barbeiro,
        barbearia,
        cliente,
        servico,
        agendamento,
        conversa
    )
    Base.metadata.create_all(bind=engine)
    _ensure_clientes_contexto_column()


def _ensure_clientes_contexto_column():
    # Backward-compatible schema fix for deployments created before `clientes.contexto`.
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE clientes ADD COLUMN contexto JSON NULL"))
    except Exception:
        # Ignore if the column already exists or if DB dialect does not support JSON ALTER syntax.
        pass
