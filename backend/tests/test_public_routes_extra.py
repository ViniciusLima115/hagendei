"""Testes adicionais para rotas públicas — cobre paths de erro e endpoints não testados."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.agendamento import Agendamento
from app.models.estabelecimento import Estabelecimento
from app.models.barbeiro import Barbeiro
from app.models.cliente import Cliente
from app.models.pagamento import Pagamento
from app.models.servico import Servico
from app.services.tenant_access_service import BUSINESS_TIMEZONE


# ── helpers ───────────────────────────────────────────────────────────────────

def _estabelecimento(db_session, slug="pub-extra", nome="Pub Extra"):
    b = Estabelecimento(nome=nome, slug=slug, endereco="Rua Extra")
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    return b


def _barbeiro(db_session, estabelecimento_id, nome="Barber", ativo=True):
    b = Barbeiro(nome=nome, estabelecimento_id=estabelecimento_id, ativo=ativo)
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    return b


def _servico(db_session, estabelecimento_id, nome="Corte", duracao=30, preco=40.0):
    s = Servico(nome=nome, duracao_minutos=duracao, preco=preco, estabelecimento_id=estabelecimento_id)
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


def _data_futura(days=3) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _agendamento(
    db_session,
    *,
    estabelecimento_id,
    barbeiro_id,
    servico_id,
    cliente_id,
    inicio=None,
    status="pendente",
):
    inicio = inicio or datetime.now().replace(microsecond=0) + timedelta(days=3)
    agendamento = Agendamento(
        cliente_id=cliente_id,
        profissional_id=barbeiro_id,
        servico_id=servico_id,
        estabelecimento_id=estabelecimento_id,
        cliente_nome="Cliente Publico",
        cliente_telefone="11999990020",
        data=inicio.date(),
        hora_inicio=inicio.time(),
        data_hora_inicio=inicio,
        data_hora_fim=inicio + timedelta(minutes=30),
        status=status,
    )
    db_session.add(agendamento)
    db_session.commit()
    db_session.refresh(agendamento)
    return agendamento


@pytest.mark.parametrize(
    ("status_manual", "vencimento_em"),
    [
        ("inativo", datetime.now(BUSINESS_TIMEZONE).date() + timedelta(days=30)),
        ("ativo", datetime.now(BUSINESS_TIMEZONE).date() - timedelta(days=1)),
    ],
)
def test_conta_indisponivel_nao_e_exposta_nos_endpoints_publicos(
    client,
    db_session,
    status_manual,
    vencimento_em,
):
    estabelecimento = _estabelecimento(
        db_session,
        f"indisponivel-{status_manual}-{vencimento_em.day}",
    )
    barbeiro = _barbeiro(db_session, estabelecimento.id)
    servico = _servico(db_session, estabelecimento.id)
    estabelecimento.status_manual = status_manual
    estabelecimento.vencimento_em = vencimento_em
    db_session.commit()

    payload = {
        "estabelecimento_id": estabelecimento.id,
        "cliente_nome": "Cliente Bloqueado",
        "cliente_telefone": "11999990021",
        "barbeiro_id": barbeiro.id,
        "servico_id": servico.id,
        "data": _data_futura(),
        "hora_inicio": "10:00",
    }
    respostas = [
        client.get(f"/public/estabelecimento/{estabelecimento.slug}"),
        client.get(f"/public/estabelecimento-id/{estabelecimento.id}"),
        client.get("/public/servicos", params={"estabelecimento_id": estabelecimento.id}),
        client.get("/public/barbeiros", params={"estabelecimento_id": estabelecimento.id}),
        client.get(
            "/public/horarios-disponiveis",
            params={
                "estabelecimento_id": estabelecimento.id,
                "barbeiro_id": barbeiro.id,
                "servico_id": servico.id,
                "data": _data_futura(),
            },
        ),
        client.post("/public/agendamentos", json=payload),
        client.post("/public/agendamentos/pagamento/iniciar", json=payload),
    ]

    assert all(resposta.status_code == 404 for resposta in respostas)
    assert {
        resposta.json()["detail"] for resposta in respostas
    } == {"Estabelecimento nao encontrado."}


def test_conta_inativa_oculta_token_e_status_de_pagamento_publicos(client, db_session):
    estabelecimento = _estabelecimento(db_session, "inativa-token-pagamento")
    barbeiro = _barbeiro(db_session, estabelecimento.id)
    servico = _servico(db_session, estabelecimento.id)
    cliente = Cliente(
        telefone="11999990022",
        nome="Cliente Token",
        estabelecimento_id=estabelecimento.id,
    )
    db_session.add(cliente)
    db_session.commit()
    db_session.refresh(cliente)
    agendamento = _agendamento(
        db_session,
        estabelecimento_id=estabelecimento.id,
        barbeiro_id=barbeiro.id,
        servico_id=servico.id,
        cliente_id=cliente.id,
    )
    pagamento = Pagamento(
        agendamento_id=agendamento.id,
        estabelecimento_id=estabelecimento.id,
        external_reference="public-inactive-payment",
        amount=Decimal("40.00"),
        platform_fee_amount=Decimal("0.00"),
    )
    db_session.add(pagamento)
    estabelecimento.status_manual = "inativo"
    db_session.commit()

    token = client.get(f"/agendamentos/{agendamento.confirmation_token}/dados")
    pagamento_status = client.get(
        "/public/pagamentos/status",
        params={"external_reference": pagamento.external_reference},
    )

    assert token.status_code == 404
    assert pagamento_status.status_code == 404
    assert pagamento_status.json() == {"detail": "Pagamento nao encontrado."}


def test_agendamento_publico_respeita_limite_mensal_do_plano_gratis(
    monkeypatch,
    client,
    db_session,
):
    import app.services.public_booking_service as svc

    monkeypatch.setattr(svc, "enviar_mensagem_whatsapp", lambda *a, **kw: True)
    estabelecimento = _estabelecimento(db_session, "quota-publica")
    estabelecimento.plano = "gratis"
    barbeiro = _barbeiro(db_session, estabelecimento.id)
    servico = _servico(db_session, estabelecimento.id)
    cliente = Cliente(
        telefone="11999990023",
        nome="Cliente Quota",
        estabelecimento_id=estabelecimento.id,
    )
    db_session.add(cliente)
    db_session.commit()
    db_session.refresh(cliente)

    inicio = datetime.combine(date.today(), datetime.min.time()).replace(hour=8)
    db_session.add_all(
        [
            Agendamento(
                cliente_id=cliente.id,
                profissional_id=barbeiro.id,
                servico_id=servico.id,
                estabelecimento_id=estabelecimento.id,
                cliente_nome=cliente.nome,
                cliente_telefone=cliente.telefone,
                data=inicio.date(),
                hora_inicio=(inicio + timedelta(minutes=30 * indice)).time(),
                data_hora_inicio=inicio + timedelta(minutes=30 * indice),
                data_hora_fim=inicio + timedelta(minutes=30 * (indice + 1)),
                status="cancelado",
            )
            for indice in range(30)
        ]
    )
    db_session.commit()

    resposta = client.post(
        "/public/agendamentos",
        json={
            "estabelecimento_id": estabelecimento.id,
            "cliente_nome": "Novo Cliente",
            "cliente_telefone": "11999990024",
            "barbeiro_id": barbeiro.id,
            "servico_id": servico.id,
            "data": _data_futura(),
            "hora_inicio": "10:00",
        },
    )

    assert resposta.status_code == 403
    assert "Limite de 30 agendamentos por mes atingido" in resposta.json()["detail"]


# ── GET /public/estabelecimento/{slug} — error paths ─────────────────────────

def test_lookup_estabelecimento_slug_invalido_retorna_404(client):
    resp = client.get("/public/estabelecimento/slug-inexistente-xyz")
    assert resp.status_code == 404


def test_lookup_estabelecimento_slug_sem_params_retorna_200(client, db_session):
    b = _estabelecimento(db_session, "sem-params")
    resp = client.get(f"/public/estabelecimento/{b.slug}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "sem-params"


def test_lookup_publico_retorna_identidade_visual(client, db_session):
    b = _estabelecimento(db_session, "tema-publico")
    b.accent_color = "#db2777"
    b.bg_color = "#fff5fa"
    b.logo_url = "https://example.com/tenant-logo.png"
    db_session.commit()

    por_slug = client.get(f"/public/estabelecimento/{b.slug}")
    por_id = client.get(f"/public/estabelecimento-id/{b.id}")

    assert por_slug.status_code == 200
    assert por_id.status_code == 200
    for body in (por_slug.json(), por_id.json()):
        assert body["accent_color"] == "#db2777"
        assert body["bg_color"] == "#fff5fa"
        assert body["logo_url"] == "https://example.com/tenant-logo.png"


# ── GET /public/estabelecimento-id/{estabelecimento_id} ──────────────────────

def test_lookup_estabelecimento_por_id_retorna_200(client, db_session):
    b = _estabelecimento(db_session, "por-id-1", "Por Id")
    resp = client.get(f"/public/estabelecimento-id/{b.id}")
    assert resp.status_code == 200
    assert resp.json()["estabelecimento_id"] == b.id


def test_lookup_estabelecimento_por_id_invalido_retorna_404(client):
    resp = client.get("/public/estabelecimento-id/999999")
    assert resp.status_code == 404


def test_lookup_estabelecimento_por_id_com_data_e_params(client, db_session):
    b = _estabelecimento(db_session, "por-id-2", "Com Params")
    barb = _barbeiro(db_session, b.id)
    serv = _servico(db_session, b.id)
    resp = client.get(
        f"/public/estabelecimento-id/{b.id}",
        params={"barbeiro_id": barb.id, "servico_id": serv.id, "data": _data_futura()},
    )
    assert resp.status_code == 200


# ── GET /public/{estabelecimento_id}/cliente ───────────────────────────────────────

def test_lookup_cliente_nao_permite_enumerar_cadastro_existente(client, db_session):
    b = _estabelecimento(db_session, "cliente-lookup")
    c = Cliente(telefone="11999990001", nome="Joana", estabelecimento_id=b.id)
    db_session.add(c)
    db_session.commit()

    resp = client.get(f"/public/{b.id}/cliente", params={"telefone": "11999990001"})
    assert resp.status_code == 404


def test_lookup_cliente_retorna_404_quando_nao_existe(client, db_session):
    b = _estabelecimento(db_session, "cliente-vazio")
    resp = client.get(f"/public/{b.id}/cliente", params={"telefone": "99999999999"})
    assert resp.status_code == 404


# ── POST /public/agendamentos — error paths ───────────────────────────────────

def test_agendamento_estabelecimento_invalida_retorna_400_ou_422(monkeypatch, client, db_session):
    import app.services.public_booking_service as svc
    monkeypatch.setattr(svc, "enviar_mensagem_whatsapp", lambda *a, **kw: True)

    resp = client.post(
        "/public/agendamentos",
        json={
            "estabelecimento_id": 999999,
            "cliente_nome": "Teste",
            "cliente_telefone": "11999990002",
            "barbeiro_id": 1,
            "servico_id": 1,
            "data": _data_futura(),
            "hora_inicio": "10:00",
        },
    )
    assert resp.status_code in (400, 404, 422)


def test_agendamento_sem_campos_obrigatorios_retorna_422(client):
    resp = client.post("/public/agendamentos", json={"estabelecimento_id": 1})
    assert resp.status_code == 422


def test_agendamento_horario_bloqueado_por_conflito_retorna_400(monkeypatch, client, db_session):
    import app.services.public_booking_service as svc
    monkeypatch.setattr(svc, "enviar_mensagem_whatsapp", lambda *a, **kw: True)

    b = _estabelecimento(db_session, "conflito-test")
    barb = _barbeiro(db_session, b.id)
    serv = _servico(db_session, b.id, duracao=30)
    data = _data_futura(days=5)

    payload = {
        "estabelecimento_id": b.id,
        "cliente_nome": "Primeiro",
        "cliente_telefone": "11999990010",
        "barbeiro_id": barb.id,
        "servico_id": serv.id,
        "data": data,
        "hora_inicio": "10:00",
    }
    resp1 = client.post("/public/agendamentos", json=payload)
    assert resp1.status_code == 200

    payload["cliente_nome"] = "Segundo"
    payload["cliente_telefone"] = "11999990011"
    resp2 = client.post("/public/agendamentos", json=payload)
    assert resp2.status_code == 400


# ── GET /public/horarios-disponiveis — additional paths ───────────────────────

def test_horarios_com_barbeiro_retorna_200(client, db_session):
    b = _estabelecimento(db_session, "horarios-com-barb")
    barb = _barbeiro(db_session, b.id)
    serv = _servico(db_session, b.id)
    resp = client.get(
        "/public/horarios-disponiveis",
        params={"estabelecimento_id": b.id, "barbeiro_id": barb.id, "servico_id": serv.id, "data": _data_futura()},
    )
    assert resp.status_code == 200


def test_horarios_estabelecimento_invalida_retorna_400_ou_422(client):
    resp = client.get(
        "/public/horarios-disponiveis",
        params={"estabelecimento_id": 999999, "servico_id": 1, "data": "2030-01-01"},
    )
    assert resp.status_code in (400, 404, 422)
