from app.models.estabelecimento import Estabelecimento
from app.security import hash_senha, verificar_senha


def test_estabelecimentos_exige_admin_e_bloqueia_tenant(client, make_tenant_headers):
    sem_auth = client.get("/estabelecimentos/")
    assert sem_auth.status_code == 401

    tenant_auth = client.get("/estabelecimentos/", headers=make_tenant_headers(tenant_id=1))
    assert tenant_auth.status_code == 401


def test_estabelecimentos_crud_admin(client, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)

    criar = client.post(
        "/estabelecimentos/",
        headers=admin_headers,
        json={
            "nome": "Estabelecimento Centro",
            "login": "estabelecimento.centro",
            "senha": "senha-segura",
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
    estabelecimento_id = created["id"]
    assert created["login"] == "estabelecimento.centro"

    listar = client.get("/estabelecimentos/", headers=admin_headers)
    assert listar.status_code == 200
    assert any(item["id"] == estabelecimento_id for item in listar.json())

    atualizar = client.put(
        f"/estabelecimentos/{estabelecimento_id}",
        headers=admin_headers,
        json={
            "nome": "Estabelecimento Centro Atualizado",
            "login": "estabelecimento.centro",
            "senha": "senha-nova",
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
    assert updated["nome"] == "Estabelecimento Centro Atualizado"
    assert updated["plano"] == "premium"

    remover = client.delete(f"/estabelecimentos/{estabelecimento_id}", headers=admin_headers)
    assert remover.status_code == 204


def test_estabelecimentos_valida_duplicidades(client, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)

    payload_base = {
        "nome": "Estabelecimento A",
        "login": "estabelecimento.a",
        "senha": "senha-segura",
        "plano": "basico",
        "status_manual": "ativo",
        "vencimento_em": "2026-12-31",
        "trial_ativo": False,
        "trial_fim_em": None,
        "ultimo_acesso_em": None,
        "pagamento_recusado": False,
        "endereco": "Rua A",
    }
    primeira = client.post("/estabelecimentos/", headers=admin_headers, json=payload_base)
    assert primeira.status_code == 200

    duplicada_login = dict(payload_base)
    r_login = client.post("/estabelecimentos/", headers=admin_headers, json=duplicada_login)
    assert r_login.status_code == 400

    sem_conflito = dict(payload_base)
    sem_conflito["login"] = "estabelecimento.b"
    r_ok = client.post("/estabelecimentos/", headers=admin_headers, json=sem_conflito)
    assert r_ok.status_code == 200


def test_estabelecimentos_crud_cria_com_senha_hasheada(client, db_session, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)

    payload = {
        "nome": "Teste Hash",
        "login": "teste.hash",
        "senha": "senha_plain",
        "plano": "basico",
        "status_manual": "ativo",
        "vencimento_em": "2027-01-01",
        "trial_ativo": False,
        "pagamento_recusado": False,
        "endereco": "Rua B",
    }
    resp = client.post("/estabelecimentos/", json=payload, headers=admin_headers)
    assert resp.status_code == 200

    criada = db_session.query(Estabelecimento).filter(Estabelecimento.login == "teste.hash").first()
    assert criada is not None
    assert criada.senha != "senha_plain"
    assert verificar_senha("senha_plain", criada.senha)


def test_estabelecimentos_crud_atualiza_com_senha_hasheada(client, db_session, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)
    estabelecimento = Estabelecimento(
        nome="Para Atualizar",
        login="para.atualizar",
        senha=hash_senha("senha_original"),
        plano="basico",
        endereco="Rua C",
    )
    db_session.add(estabelecimento)
    db_session.commit()
    db_session.refresh(estabelecimento)

    payload = {
        "nome": "Para Atualizar",
        "login": "para.atualizar",
        "senha": "senha_nova",
        "plano": "basico",
        "status_manual": "ativo",
        "vencimento_em": "2027-01-01",
        "trial_ativo": False,
        "pagamento_recusado": False,
        "endereco": "Rua C",
    }
    resp = client.put(f"/estabelecimentos/{estabelecimento.id}", json=payload, headers=admin_headers)
    assert resp.status_code == 200

    db_session.refresh(estabelecimento)
    assert estabelecimento.senha != "senha_nova"
    assert verificar_senha("senha_nova", estabelecimento.senha)
