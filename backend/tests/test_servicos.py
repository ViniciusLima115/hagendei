def test_atualizar_servico(client, tenant_headers):
    criar = client.post(
        "/servicos/",
        json={"nome": "Corte", "duracao_minutos": 30, "preco": 35.0},
        headers=tenant_headers,
    )
    assert criar.status_code == 200
    servico_id = criar.json()["id"]

    resp = client.put(
        f"/servicos/{servico_id}",
        json={"nome": "Corte Premium", "duracao_minutos": 45, "preco": 50.0},
        headers=tenant_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Corte Premium"
    assert resp.json()["preco"] == 50.0


def test_atualizar_servico_nao_encontrado(client, tenant_headers):
    resp = client.put(
        "/servicos/99999",
        json={"nome": "Nao existe", "duracao_minutos": 30, "preco": 10.0},
        headers=tenant_headers,
    )
    assert resp.status_code == 404


def test_remover_servico(client, tenant_headers):
    criar = client.post(
        "/servicos/",
        json={"nome": "Barba Simples", "duracao_minutos": 20, "preco": 20.0},
        headers=tenant_headers,
    )
    assert criar.status_code == 200
    servico_id = criar.json()["id"]

    resp = client.delete(f"/servicos/{servico_id}", headers=tenant_headers)
    assert resp.status_code == 204


def test_remover_servico_nao_encontrado(client, tenant_headers):
    resp = client.delete("/servicos/99999", headers=tenant_headers)
    assert resp.status_code == 404
