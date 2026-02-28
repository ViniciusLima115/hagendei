import hashlib
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent


class WebhookEventRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def extract_event_id(payload: dict) -> str:
        entry = payload.get("entry", [])
        mensagem_id = None
        if entry:
            try:
                mensagem_id = entry[0].get("changes", [])[0].get("value", {}).get("messages", [])[0].get("id")
            except Exception:
                mensagem_id = None

        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        candidates = [
            payload.get("event_id"),
            payload.get("eventId"),
            payload.get("id"),
            data.get("id"),
            data.get("event_id"),
            data.get("eventId"),
            data.get("key", {}).get("id") if isinstance(data.get("key"), dict) else None,
            mensagem_id,
        ]

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def register_event_once(
        self,
        *,
        provider: str,
        event_id: str,
        tenant_id: int | None,
    ) -> bool:
        event = WebhookEvent(provider=provider, event_id=event_id, tenant_id=tenant_id)
        self.db.add(event)
        try:
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            return False
