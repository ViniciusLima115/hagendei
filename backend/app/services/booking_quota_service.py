from datetime import date

from sqlalchemy.orm import Session

from app.models.agendamento import Agendamento
from app.models.estabelecimento import Estabelecimento


LIMITE_AGENDAMENTOS_GRATIS = 30


class LimiteAgendamentosPlanoError(ValueError):
    pass


def validar_limite_mensal_agendamentos(
    db: Session,
    *,
    estabelecimento: Estabelecimento,
) -> None:
    if (estabelecimento.plano or "gratis").strip().lower() != "gratis":
        return

    # Serializa criacoes concorrentes do mesmo tenant no PostgreSQL para que
    # duas requisicoes nao ultrapassem a quota ao mesmo tempo.
    db.query(Estabelecimento.id).filter(
        Estabelecimento.id == estabelecimento.id
    ).with_for_update().first()

    inicio_mes = date.today().replace(day=1)
    inicio_proximo_mes = (
        date(inicio_mes.year + 1, 1, 1)
        if inicio_mes.month == 12
        else date(inicio_mes.year, inicio_mes.month + 1, 1)
    )
    total_mes = (
        db.query(Agendamento)
        .filter(
            Agendamento.estabelecimento_id == estabelecimento.id,
            Agendamento.data >= inicio_mes,
            Agendamento.data < inicio_proximo_mes,
        )
        .count()
    )
    if total_mes >= LIMITE_AGENDAMENTOS_GRATIS:
        raise LimiteAgendamentosPlanoError(
            f"Limite de {LIMITE_AGENDAMENTOS_GRATIS} agendamentos por mes atingido "
            "no plano Gratis. Faca o upgrade para continuar."
        )
