import os
import re

import requests
from fastapi import APIRouter, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.barbearia import Barbearia
from app.services.chatbot_service import responder_mensagem

router = APIRouter()

VERIFY_TOKEN = "barbearia_token_123"

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)

    return {"status": "error"}


@router.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()

    try:
        print("WEBHOOK BODY:", body)
        telefone, texto, value = _extrair_dados_mensagem(body)

        if not telefone or not texto:
            return {"status": "ignored"}

        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        whatsapp_number = value.get("metadata", {}).get("display_phone_number") or phone_number_id
        instance_key = _extrair_instance_key(body, value)

        db = SessionLocal()
        try:
            tenant_id = _resolver_tenant_id(
                db,
                instance_key=instance_key,
                whatsapp_number=whatsapp_number,
            )
            if tenant_id is None:
                print("Webhook ignorado: tenant_id nao resolvido.")
                return {"status": "ignored"}

            resposta = responder_mensagem(db, telefone, texto, tenant_id=tenant_id)
        finally:
            db.close()

        texto_resposta = resposta.get("resposta", "") if isinstance(resposta, dict) else str(resposta)
        enviar_resposta_whatsapp(telefone, texto_resposta, phone_number_id=phone_number_id)

    except Exception as e:
        print("Erro webhook:", e)

    return {"status": "ok"}


def _extrair_dados_mensagem(body: dict) -> tuple[str | None, str | None, dict]:
    entry = body.get("entry", [])
    if entry:
        changes = entry[0].get("changes", [])
        if not changes:
            return None, None, {}

        value = changes[0].get("value", {})
        messages = value.get("messages")
        if not messages:
            return None, None, value

        mensagem = messages[0]
        if mensagem.get("type") != "text":
            return None, None, value

        telefone = mensagem.get("from")
        texto = mensagem.get("text", {}).get("body")
        return telefone, texto, value

    # Fallback para formatos comuns de webhook (MegaAPI/Evolution-like).
    data = body.get("data", {}) if isinstance(body.get("data", {}), dict) else {}
    data_message = data.get("message", {}) if isinstance(data.get("message", {}), dict) else {}
    telefone = (
        body.get("from")
        or body.get("sender")
        or data.get("from")
        or data.get("sender")
        or data.get("key", {}).get("remoteJid")
        or body.get("remoteJid")
    )
    texto = (
        body.get("text")
        or body.get("message")
        or body.get("body")
        or data.get("text")
        or data.get("body")
        or data_message.get("conversation")
        or data_message.get("extendedTextMessage", {}).get("text")
    )
    return telefone, texto, {}


def _extrair_instance_key(body: dict, value: dict) -> str | None:
    candidatos = [
        body.get("instance_key"),
        body.get("instanceKey"),
        body.get("instance"),
        body.get("instance", {}).get("key") if isinstance(body.get("instance"), dict) else None,
        body.get("instance", {}).get("instance_key") if isinstance(body.get("instance"), dict) else None,
        body.get("instance", {}).get("instanceKey") if isinstance(body.get("instance"), dict) else None,
        body.get("data", {}).get("instance_key") if isinstance(body.get("data"), dict) else None,
        body.get("data", {}).get("instanceKey") if isinstance(body.get("data"), dict) else None,
        value.get("instance_key"),
        value.get("instanceKey"),
        value.get("instance"),
        value.get("instance", {}).get("key") if isinstance(value.get("instance"), dict) else None,
        value.get("instance", {}).get("instance_key") if isinstance(value.get("instance"), dict) else None,
        value.get("instance", {}).get("instanceKey") if isinstance(value.get("instance"), dict) else None,
        value.get("metadata", {}).get("instance_key"),
        value.get("metadata", {}).get("instanceKey"),
    ]
    for candidato in candidatos:
        if isinstance(candidato, str) and candidato.strip():
            return candidato.strip()

    return None


def _normalizar_whatsapp(valor: str | None) -> str | None:
    if valor is None:
        return None
    digits = re.sub(r"\D", "", str(valor))
    return digits or None


def _resolver_tenant_id(
    db: Session,
    instance_key: str | None = None,
    whatsapp_number: str | None = None,
) -> int | None:
    if instance_key:
        barbearia = (
            db.query(Barbearia)
            .filter(Barbearia.mega_instance_key == instance_key.strip())
            .first()
        )
        if barbearia:
            return barbearia.id

    numero_bruto = whatsapp_number.strip() if isinstance(whatsapp_number, str) else None
    numero_normalizado = _normalizar_whatsapp(whatsapp_number)
    if numero_bruto or numero_normalizado:
        filtros = []
        if numero_bruto:
            filtros.append(Barbearia.whatsapp_number == numero_bruto)
        if numero_normalizado and numero_normalizado != numero_bruto:
            filtros.append(Barbearia.whatsapp_number == numero_normalizado)

        barbearia = db.query(Barbearia).filter(or_(*filtros)).first()
        if barbearia:
            return barbearia.id

    return None


def enviar_resposta_whatsapp(telefone, texto, phone_number_id: str | None = None):
    telefone = re.sub(r"\D", "", str(telefone))
    current_phone_number_id = phone_number_id or PHONE_NUMBER_ID

    if not current_phone_number_id:
        print("Nao foi possivel enviar mensagem: PHONE_NUMBER_ID ausente.")
        return

    url = f"https://graph.facebook.com/v22.0/{current_phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    data = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": texto},
    }

    response = requests.post(url, headers=headers, json=data)

    print("STATUS META:", response.status_code)
    print("RESPOSTA META:", response.text)
