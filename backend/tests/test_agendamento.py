from datetime import datetime, timedelta


def test_criar_agendamento_com_sucesso(client, dados_base):
    inicio = (dados_base["amanha"].replace(hour=14, minute=0, second=0, microsecond=0)).isoformat()
    payload = {
        "telefone": "5582999999999",
        "nome_cliente": "Vinicius",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio,
        "status": "confirmado",
    }

    resp = client.post("/agendamentos/", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "confirmado"
    assert body["servico_nome"] == "corte social"
    assert body["cliente_nome"] == "Vinicius"


def test_criar_agendamento_com_conflito(client, dados_base):
    inicio = dados_base["amanha"].replace(hour=14, minute=0, second=0, microsecond=0)
    payload_1 = {
        "telefone": "5582999999999",
        "nome_cliente": "Cliente 1",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "confirmado",
    }
    payload_2 = {
        "telefone": "5582988888888",
        "nome_cliente": "Cliente 2",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": (inicio + timedelta(minutes=20)).isoformat(),
        "status": "confirmado",
    }

    first = client.post("/agendamentos/", json=payload_1)
    assert first.status_code == 200

    second = client.post("/agendamentos/", json=payload_2)
    assert second.status_code == 400
    assert second.json()["detail"] == "Horário indisponível"


def test_atualizar_status_agendamento(client, dados_base):
    inicio = dados_base["amanha"].replace(hour=15, minute=0, second=0, microsecond=0)
    payload = {
        "telefone": "5582977777777",
        "nome_cliente": "Cliente Status",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "confirmado",
    }
    created = client.post("/agendamentos/", json=payload).json()

    resp = client.patch(
        f"/agendamentos/{created['id']}/status",
        json={"status": "cancelado"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelado"


def test_atualizar_status_agendamento_inexistente(client):
    resp = client.patch("/agendamentos/9999/status", json={"status": "cancelado"})
    assert resp.status_code == 404
