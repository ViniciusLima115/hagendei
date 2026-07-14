import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import is_production_env
from app.database import get_db
from app.services.notificacao_service import processar_lembretes_pendentes
from app.services.payments.payment_service import expire_pending_appointments


router = APIRouter(prefix="/internal", tags=["internal"])


<<<<<<< HEAD
def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    expected = os.getenv("INTERNAL_REMINDER_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Endpoint interno nao configurado.")
    if not x_internal_token or not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=401, detail="Token interno invalido.")


@router.post("/reminders/process")
def processar_reminders(
    _: None = Depends(require_internal_token),
    limite: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
=======
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
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    return processar_lembretes_pendentes(db, limite=limite)


@router.post("/payments/expire-pending")
def expire_pending_payments(
    _: None = Depends(require_internal_token),
    limite: int = Query(default=300, ge=1, le=500),
    db: Session = Depends(get_db),
):
<<<<<<< HEAD
    expirados = expire_pending_bookings_and_payments(db, limit=limite)
=======
    _validar_token_interno(x_internal_token)
    expirados = expire_pending_appointments(db, limit=limite)
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    return {"expirados": expirados}
