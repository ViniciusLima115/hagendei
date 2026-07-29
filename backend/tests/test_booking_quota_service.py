from datetime import date, datetime, time, timedelta

import pytest

from app.models.agendamento import Agendamento
from app.models.cliente import Cliente
from app.services.booking_quota_service import (
    LimiteAgendamentosPlanoError,
    validar_limite_mensal_agendamentos,
)


def _inicio_proximo_mes() -> date:
    hoje = date.today()
    return (
        date(hoje.year + 1, 1, 1)
        if hoje.month == 12
        else date(hoje.year, hoje.month + 1, 1)
    )


def _agendamentos(
    *,
    quantidade: int,
    dia: date,
    cliente_id: int,
    profissional_id: int,
    servico_id: int,
    estabelecimento_id: int,
) -> list[Agendamento]:
    inicio_base = datetime.combine(dia, time(hour=8))
    return [
        Agendamento(
            cliente_id=cliente_id,
            profissional_id=profissional_id,
            servico_id=servico_id,
            estabelecimento_id=estabelecimento_id,
            cliente_nome="Cliente Quota",
            cliente_telefone="11999999999",
            data=dia,
            hora_inicio=(inicio_base + timedelta(minutes=indice)).time(),
            data_hora_inicio=inicio_base + timedelta(minutes=indice),
            data_hora_fim=inicio_base + timedelta(minutes=indice + 30),
        )
        for indice in range(quantidade)
    ]


def test_quota_gratis_considera_apenas_o_mes_corrente(db_session, dados_base):
    estabelecimento = dados_base["estabelecimento"]
    estabelecimento.plano = "gratis"
    cliente = Cliente(
        nome="Cliente Quota",
        telefone="11999999999",
        estabelecimento_id=estabelecimento.id,
    )
    db_session.add(cliente)
    db_session.flush()

    db_session.add_all(
        _agendamentos(
            quantidade=30,
            dia=_inicio_proximo_mes(),
            cliente_id=cliente.id,
            profissional_id=dados_base["barbeiro"].id,
            servico_id=dados_base["servico"].id,
            estabelecimento_id=estabelecimento.id,
        )
    )
    db_session.commit()

    validar_limite_mensal_agendamentos(
        db_session,
        estabelecimento=estabelecimento,
    )

    db_session.add_all(
        _agendamentos(
            quantidade=30,
            dia=date.today(),
            cliente_id=cliente.id,
            profissional_id=dados_base["barbeiro"].id,
            servico_id=dados_base["servico"].id,
            estabelecimento_id=estabelecimento.id,
        )
    )
    db_session.commit()

    with pytest.raises(LimiteAgendamentosPlanoError):
        validar_limite_mensal_agendamentos(
            db_session,
            estabelecimento=estabelecimento,
        )
