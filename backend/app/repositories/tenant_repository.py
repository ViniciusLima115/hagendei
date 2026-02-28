from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.barbearia import Barbearia


class TenantRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, tenant_id: int) -> Barbearia | None:
        return self.db.query(Barbearia).filter(Barbearia.id == tenant_id).first()

    def get_by_slug(self, slug: str) -> Barbearia | None:
        return self.db.query(Barbearia).filter(Barbearia.slug == slug.strip().lower()).first()

    def resolve_by_instance_or_whatsapp(
        self,
        *,
        instance_key: str | None = None,
        whatsapp_number: str | None = None,
    ) -> Barbearia | None:
        if instance_key:
            by_instance = (
                self.db.query(Barbearia)
                .filter(Barbearia.mega_instance_key == instance_key.strip())
                .first()
            )
            if by_instance:
                return by_instance

        if not whatsapp_number:
            return None

        numero_bruto = whatsapp_number.strip()
        numero_normalizado = "".join(ch for ch in numero_bruto if ch.isdigit())
        filtros = [Barbearia.whatsapp_number == numero_bruto]
        if numero_normalizado and numero_normalizado != numero_bruto:
            filtros.append(Barbearia.whatsapp_number == numero_normalizado)

        return self.db.query(Barbearia).filter(or_(*filtros)).first()
