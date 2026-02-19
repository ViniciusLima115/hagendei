from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.config import HORARIO_ABERTURA, HORARIO_FECHAMENTO, INTERVALO_MINUTOS
from app.models.agendamento import Agendamento
from app.models.servico import Servico


def gerar_horarios_disponiveis(
    db: Session,
    barbeiro_id: int,
    servico_id: int,
    data: datetime,
):
    servico = db.query(Servico).filter(Servico.id == servico_id).first()
    if not servico:
        return []

    duracao = servico.duracao_minutos

    inicio_dia = datetime.combine(data.date(), time(HORARIO_ABERTURA, 0))
    fim_dia = datetime.combine(data.date(), time(HORARIO_FECHAMENTO, 0))

    horarios = []
    atual = inicio_dia

    while atual + timedelta(minutes=duracao) <= fim_dia:
        horarios.append(atual)
        atual += timedelta(minutes=INTERVALO_MINUTOS)

    agendamentos = (
        db.query(Agendamento)
        .filter(
            Agendamento.barbeiro_id == barbeiro_id,
            Agendamento.data_hora_inicio >= inicio_dia,
            Agendamento.data_hora_inicio < fim_dia,
        )
        .all()
    )

    livres = []

    for horario in horarios:
        fim_slot = horario + timedelta(minutes=duracao)

        conflito = False
        for ag in agendamentos:
            if ag.data_hora_inicio < fim_slot and ag.data_hora_fim > horario:
                conflito = True
                break

        if not conflito:
            livres.append(horario.strftime("%H:%M"))

    return livres
