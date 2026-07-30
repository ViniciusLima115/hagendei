from datetime import datetime, timedelta

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.estabelecimento import Estabelecimento
from app.models.cliente import Cliente
from app.models.reminder_job import ReminderJob
from app.models.servico import Servico
from app.services import scheduler as scheduler_service
from app.services import notificacao_service
from app.services.notificacao_service import processar_lembretes_pendentes
from app.services.scheduler import processar_lembretes_email_pendentes


def test_scheduler_processa_lembretes_whatsapp(monkeypatch):
    class FakeSession:
        closed = False

        def close(self):
            self.closed = True

    fake_session = FakeSession()
    chamadas: list[object] = []
    monkeypatch.setattr(scheduler_service, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(
        scheduler_service,
        "processar_lembretes_pendentes",
        lambda db: chamadas.append(db) or {"processados": 1, "enviados": 1, "falhas": 0},
    )

    scheduler_service._processar_lembretes_whatsapp()

    assert chamadas == [fake_session]
    assert fake_session.closed is True


def test_scheduler_envia_lembrete_24h(monkeypatch, db_session):
    enviados: list[dict[str, str]] = []

    def fake_send(payload):
        enviados.append(payload)
        return True

    monkeypatch.setattr("app.services.scheduler.send_email_payload", fake_send)
    monkeypatch.setattr("app.services.scheduler.SessionLocal", lambda: db_session)

    estabelecimento = Estabelecimento(nome="Estabelecimento Scheduler", slug="scheduler", endereco="Rua Scheduler")
    db_session.add(estabelecimento)
    db_session.commit()
    db_session.refresh(estabelecimento)

    barbeiro = Barbeiro(nome="Mauro", estabelecimento_id=estabelecimento.id, ativo=True)
    servico = Servico(nome="Barba", duracao_minutos=30, preco=35.0, estabelecimento_id=estabelecimento.id)
    cliente = Cliente(nome="Cliente Scheduler", telefone="5582992222222", estabelecimento_id=estabelecimento.id)
    db_session.add_all([barbeiro, servico, cliente])
    db_session.commit()
    db_session.refresh(barbeiro)
    db_session.refresh(servico)
    db_session.refresh(cliente)

    inicio = datetime.now() + timedelta(hours=24)
    agendamento = Agendamento(
        cliente_id=cliente.id,
        barbeiro_id=barbeiro.id,
        servico_id=servico.id,
        estabelecimento_id=estabelecimento.id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        cliente_email="scheduler@example.com",
        data=inicio.date(),
        hora_inicio=inicio.time().replace(second=0, microsecond=0),
        data_hora_inicio=inicio,
        data_hora_fim=inicio + timedelta(minutes=30),
        status="pendente",
    )
    db_session.add(agendamento)
    db_session.commit()
    db_session.refresh(agendamento)
    agendamento_id = agendamento.id

    resultado = processar_lembretes_email_pendentes()

    assert resultado["enviados"] == 1
    assert enviados
    assert enviados[0]["to_email"] == "scheduler@example.com"
    assert "Lembrete de agendamento" in enviados[0]["subject"]

    # scheduler calls db.close() which expunges objects — re-query instead of refresh
    agendamento_atualizado = db_session.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    assert agendamento_atualizado.lembrete_24h_enviado is True
    assert agendamento_atualizado.lembrete_2h_enviado is False


def test_whatsapp_faz_retry_antes_de_marcar_falha(
    monkeypatch,
    db_session,
    dados_base,
):
    estabelecimento = dados_base["estabelecimento"]
    estabelecimento.plano = "profissional"
    cliente = Cliente(
        nome="Cliente Retry",
        telefone="5582999999999",
        estabelecimento_id=estabelecimento.id,
    )
    db_session.add(cliente)
    db_session.flush()

    inicio = datetime.now() + timedelta(hours=3)
    agendamento = Agendamento(
        cliente_id=cliente.id,
        profissional_id=dados_base["barbeiro"].id,
        servico_id=dados_base["servico"].id,
        estabelecimento_id=estabelecimento.id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        data=inicio.date(),
        hora_inicio=inicio.time().replace(second=0, microsecond=0),
        data_hora_inicio=inicio,
        data_hora_fim=inicio + timedelta(minutes=30),
    )
    db_session.add(agendamento)
    db_session.flush()
    job = ReminderJob(
        estabelecimento_id=estabelecimento.id,
        agendamento_id=agendamento.id,
        tipo="reminder_2h",
        canal="whatsapp",
        destinatario=cliente.telefone,
        mensagem="Teste de retry",
        enviar_em=datetime.now() - timedelta(minutes=1),
        status="pendente",
    )
    db_session.add(job)
    db_session.commit()

    monkeypatch.setenv("REMINDER_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("REMINDER_RETRY_MINUTES", "1")
    monkeypatch.setattr(notificacao_service, "enviar_mensagem_whatsapp", lambda *_: False)

    primeira = processar_lembretes_pendentes(db_session)
    db_session.refresh(job)
    assert primeira == {"processados": 1, "enviados": 0, "falhas": 1}
    assert job.status == "pendente"
    assert job.tentativas == 1
    assert job.enviar_em > datetime.now()

    job.enviar_em = datetime.now() - timedelta(seconds=1)
    db_session.commit()
    segunda = processar_lembretes_pendentes(db_session)
    db_session.refresh(job)
    assert segunda == {"processados": 1, "enviados": 0, "falhas": 1}
    assert job.status == "falha"
    assert job.tentativas == 2
    assert job.ultimo_erro == "falha_envio_whatsapp"
