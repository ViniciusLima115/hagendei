import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import is_production_env
from app.database import get_db
from app.services.notificacao_service import processar_lembretes_pendentes
from app.services.payments.payment_service import expire_pending_appointments


router = APIRouter(prefix="/internal", tags=["internal"])


def _validar_token_interno(x_internal_token: str | None) -> None:
    token_esperado = os.getenv("INTERNAL_REMINDER_TOKEN")
    if not token_esperado:
        if is_production_env():
            raise HTTPException(status_code=401, detail="Token interno nao configurado.")
        return
    if x_internal_token != token_esperado:
        raise HTTPException(status_code=401, detail="Token interno invalido.")


@router.post("/reminders/process")
def processar_reminders(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    limite: int = 100,
    db: Session = Depends(get_db),
):
    _validar_token_interno(x_internal_token)
    return processar_lembretes_pendentes(db, limite=limite)


@router.post("/payments/expire-pending")
def expire_pending_payments(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    limite: int = 300,
    db: Session = Depends(get_db),
):
    _validar_token_interno(x_internal_token)
    expirados = expire_pending_appointments(db, limit=limite)
    return {"expirados": expirados}
