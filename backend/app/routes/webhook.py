from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.webhook_greeting_service import processar_webhook_saudacao
from app.services.webhook_security import read_and_verify_meta_webhook, verify_meta_challenge

router = APIRouter(tags=["webhook"])


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    return verify_meta_challenge(
        mode=hub_mode,
        provided_token=hub_verify_token,
        challenge=hub_challenge,
    )


@router.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await read_and_verify_meta_webhook(request)
    return processar_webhook_saudacao(db, payload)
