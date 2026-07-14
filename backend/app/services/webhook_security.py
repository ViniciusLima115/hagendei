import hashlib
import hmac
import json
import os

from fastapi import HTTPException, Request

MAX_WEBHOOK_BODY_BYTES = 65536


def _is_production() -> bool:
    return os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}


def verify_meta_challenge(*, mode: str | None, provided_token: str | None, challenge: str | None) -> str:
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Webhook nao configurado.")
    valid = (
        mode == "subscribe"
        and bool(provided_token)
        and hmac.compare_digest(provided_token or "", expected)
        and bool(challenge)
    )
    if not valid:
        raise HTTPException(status_code=403, detail="Verificacao de webhook invalida.")
    return challenge or ""


async def read_and_verify_meta_webhook(request: Request) -> dict:
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload de webhook excede o limite permitido.")
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload de webhook excede o limite permitido.")

    app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    allow_unsigned = (
        not _is_production()
        and os.getenv("WHATSAPP_ALLOW_UNSIGNED_WEBHOOKS", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    provided = request.headers.get("x-hub-signature-256", "")
    valid_signature = False
    if app_secret and provided.startswith("sha256="):
        expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        valid_signature = hmac.compare_digest(provided[7:], expected)
    if not valid_signature and not allow_unsigned:
        raise HTTPException(status_code=401, detail="Assinatura de webhook invalida.")

    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Payload JSON invalido.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload JSON invalido.")
    return payload
