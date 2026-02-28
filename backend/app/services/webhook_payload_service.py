import re

from sqlalchemy.orm import Session

from app.repositories.tenant_repository import TenantRepository


def extrair_dados_mensagem(body: dict) -> tuple[str | None, str | None, dict]:
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
    return telefone, texto, value if entry else {}


def extrair_instance_key(body: dict, value: dict) -> str | None:
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


def normalizar_whatsapp(valor: str | None) -> str | None:
    if valor is None:
        return None
    digits = re.sub(r"\D", "", str(valor))
    return digits or None


def resolver_tenant_id(
    db: Session,
    *,
    instance_key: str | None = None,
    whatsapp_number: str | None = None,
) -> int | None:
    repo = TenantRepository(db)
    tenant = repo.resolve_by_instance_or_whatsapp(
        instance_key=instance_key,
        whatsapp_number=whatsapp_number,
    )
    return tenant.id if tenant else None
