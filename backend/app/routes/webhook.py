import os

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.webhook_greeting_service import processar_webhook_saudacao


router = APIRouter(tags=["webhook"])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "barbearia_token_123")
    if hub_mode == "subscribe" and hub_verify_token == expected and hub_challenge:
        return int(hub_challenge)
    return {"status": "error"}


@router.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    return processar_webhook_saudacao(db, payload)
