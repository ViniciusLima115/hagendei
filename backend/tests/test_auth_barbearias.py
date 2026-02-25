from app.models.barbearia import Barbearia


def test_auth_admin_check_ok_e_invalido(client):
    ok = client.post("/auth/admin-check", json={"usuario": "vhtech_", "senha": "@dinizvascaino"})
    assert ok.status_code == 200
    assert ok.json()["is_admin"] is True

    invalido = client.post("/auth/admin-check", json={"usuario": "x", "senha": "y"})
    assert invalido.status_code == 200
    assert invalido.json()["is_admin"] is False


def test_auth_login_admin_retorna_token(client):
    resp = client.post("/auth/login", json={"usuario": "vhtech_", "senha": "@dinizvascaino"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_admin"] is True
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_auth_login_tenant_sucesso_e_senha_invalida(client, db_session):
    barbearia = Barbearia(
        nome="Barbearia Login",
        login="barbearia.login",
        senha="senha123",
        plano="basico",
        endereco="Rua A",
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    sucesso = client.post("/auth/login", json={"usuario": "barbearia.login", "senha": "senha123"})
    assert sucesso.status_code == 200
    body = sucesso.json()
    assert body["is_admin"] is False
    assert body["tenant_id"] == barbearia.id
    assert body["tenant_name"] == barbearia.nome
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    invalido = client.post("/auth/login", json={"usuario": "barbearia.login", "senha": "errada"})
    assert invalido.status_code == 401


def test_barbearias_exige_admin_e_bloqueia_tenant(client, make_tenant_headers):
    sem_auth = client.get("/barbearias/")
    assert sem_auth.status_code == 401

    tenant_auth = client.get("/barbearias/", headers=make_tenant_headers(tenant_id=1))
    assert tenant_auth.status_code == 403


def test_barbearias_crud_admin(client, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)

    criar = client.post(
        "/barbearias/",
        headers=admin_headers,
        json={
            "nome": "Barbearia Centro",
            "login": "barbearia.centro",
            "senha": "senha",
            "mega_instance_key": "inst-centro",
            "mega_token": "token-centro",
            "whatsapp_number": "5582999991111",
            "plano": "basico",
            "status_manual": "ativo",
            "vencimento_em": "2026-12-31",
            "trial_ativo": False,
            "trial_fim_em": None,
            "ultimo_acesso_em": None,
            "pagamento_recusado": False,
            "endereco": "Rua A",
        },
    )
    assert criar.status_code == 200
    created = criar.json()
    barbearia_id = created["id"]
    assert created["login"] == "barbearia.centro"
    assert created["mega_instance_key"] == "inst-centro"
    assert created["whatsapp_number"] == "5582999991111"

    listar = client.get("/barbearias/", headers=admin_headers)
    assert listar.status_code == 200
    assert any(item["id"] == barbearia_id for item in listar.json())

    atualizar = client.put(
        f"/barbearias/{barbearia_id}",
        headers=admin_headers,
        json={
            "nome": "Barbearia Centro Atualizada",
            "login": "barbearia.centro",
            "senha": "senha-nova",
            "mega_instance_key": "inst-centro",
            "mega_token": "token-centro-2",
            "whatsapp_number": "5582999991111",
            "plano": "premium",
            "status_manual": "ativo",
            "vencimento_em": "2027-01-31",
            "trial_ativo": False,
            "trial_fim_em": None,
            "ultimo_acesso_em": None,
            "pagamento_recusado": False,
            "endereco": "Rua B",
        },
    )
    assert atualizar.status_code == 200
    updated = atualizar.json()
    assert updated["nome"] == "Barbearia Centro Atualizada"
    assert updated["plano"] == "premium"

    remover = client.delete(f"/barbearias/{barbearia_id}", headers=admin_headers)
    assert remover.status_code == 204


def test_barbearias_valida_duplicidades(client, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)

    payload_base = {
        "nome": "Barbearia A",
        "login": "barbearia.a",
        "senha": "senha",
        "mega_instance_key": "inst-a",
        "mega_token": "token-a",
        "whatsapp_number": "5582999992222",
        "plano": "basico",
        "status_manual": "ativo",
        "vencimento_em": "2026-12-31",
        "trial_ativo": False,
        "trial_fim_em": None,
        "ultimo_acesso_em": None,
        "pagamento_recusado": False,
        "endereco": "Rua A",
    }
    primeira = client.post("/barbearias/", headers=admin_headers, json=payload_base)
    assert primeira.status_code == 200

    duplicada_login = dict(payload_base)
    duplicada_login["mega_instance_key"] = "inst-b"
    duplicada_login["whatsapp_number"] = "5582999993333"
    r_login = client.post("/barbearias/", headers=admin_headers, json=duplicada_login)
    assert r_login.status_code == 400

    duplicada_instancia = dict(payload_base)
    duplicada_instancia["login"] = "barbearia.c"
    duplicada_instancia["whatsapp_number"] = "5582999994444"
    r_instancia = client.post("/barbearias/", headers=admin_headers, json=duplicada_instancia)
    assert r_instancia.status_code == 400

    duplicada_whatsapp = dict(payload_base)
    duplicada_whatsapp["login"] = "barbearia.d"
    duplicada_whatsapp["mega_instance_key"] = "inst-d"
    r_whatsapp = client.post("/barbearias/", headers=admin_headers, json=duplicada_whatsapp)
    assert r_whatsapp.status_code == 400


def test_tenant_header_mismatch_retorna_403(client, dados_base, make_tenant_headers):
    token_tenant_correto = make_tenant_headers(dados_base["barbearia"].id)
    headers_mismatch = {
        **token_tenant_correto,
        "X-Barbearia-Id": str(dados_base["barbearia"].id + 999),
    }
    resp = client.get("/clientes/", headers=headers_mismatch)
    assert resp.status_code == 403
