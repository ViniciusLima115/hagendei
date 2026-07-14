import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.notificacao_service import processar_lembretes_pendentes
from app.services.payments.payment_service import expire_pending_bookings_and_payments


router = APIRouter(prefix="/internal", tags=["internal"])


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
    return processar_lembretes_pendentes(db, limite=limite)


@router.post("/payments/expire-pending")
def expire_pending_payments(
    _: None = Depends(require_internal_token),
    limite: int = Query(default=300, ge=1, le=500),
    db: Session = Depends(get_db),
):
    expirados = expire_pending_bookings_and_payments(db, limit=limite)
    return {"expirados": expirados}
