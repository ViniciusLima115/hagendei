def _funcionamento_padrao():
    return {
        "seg": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "ter": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qua": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qui": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sex": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sab": {"ativo": True, "inicio": "09:00", "fim": "14:00"},
        "dom": {"ativo": False, "inicio": "08:00", "fim": "18:00"},
    }


def test_obter_funcionamento(client, dados_base, tenant_headers, db_session):
    dados_base["barbearia"].horarios_funcionamento = _funcionamento_padrao()
    db_session.commit()

    resp = client.get("/estabelecimentos/me/funcionamento", headers=tenant_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["seg"]["ativo"] is True
    assert body["dom"]["ativo"] is False


def test_atualizar_funcionamento(client, dados_base, tenant_headers, db_session):
    payload = _funcionamento_padrao()
    payload["sab"]["ativo"] = False

    resp = client.put("/estabelecimentos/me/funcionamento", json=payload, headers=tenant_headers)
    assert resp.status_code == 200
    assert resp.json()["sab"]["ativo"] is False

    db_session.refresh(dados_base["barbearia"])
    assert dados_base["barbearia"].horarios_funcionamento["sab"]["ativo"] is False


def test_obter_funcionamento_nao_encontrado(client, make_tenant_headers):
    headers = make_tenant_headers(tenant_id=99999)
    resp = client.get("/estabelecimentos/me/funcionamento", headers=headers)
    assert resp.status_code == 404


def test_atualizar_funcionamento_nao_encontrado(client, make_tenant_headers):
    headers = make_tenant_headers(tenant_id=99999)
    resp = client.put(
        "/estabelecimentos/me/funcionamento",
        json=_funcionamento_padrao(),
        headers=headers,
    )
    assert resp.status_code == 404
