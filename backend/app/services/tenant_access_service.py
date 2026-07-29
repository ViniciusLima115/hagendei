import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.estabelecimento import Estabelecimento


BUSINESS_TIMEZONE = ZoneInfo(os.getenv("BUSINESS_TIMEZONE", "America/Sao_Paulo"))


def tenant_account_is_active(estabelecimento: Estabelecimento) -> bool:
    if (estabelecimento.status_manual or "ativo").strip().lower() != "ativo":
        return False

    today = datetime.now(BUSINESS_TIMEZONE).date()
    if estabelecimento.trial_ativo and estabelecimento.trial_fim_em:
        return estabelecimento.trial_fim_em >= today
    return not estabelecimento.vencimento_em or estabelecimento.vencimento_em >= today
