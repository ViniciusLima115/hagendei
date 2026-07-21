import pytest
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from app.limiter import limiter
from app.models.estabelecimento import Estabelecimento
import app.routes.auth as auth_module
from app.security import hash_senha


@pytest.fixture(autouse=True)
def reset_rate_limiter_storage():
    limiter._storage = MemoryStorage()
    limiter._limiter = FixedWindowRateLimiter(limiter._storage)


def test_auth_admin_check_nao_e_exposto(client):
    response = client.post(
        "/auth/admin-check",
        json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA},
    )
    assert response.status_code == 404


def test_auth_login_admin_retorna_token(client):
    resp = client.post("/auth/login", json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_admin"] is True
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_auth_login_tenant_sucesso_e_senha_invalida(client, db_session):
    estabelecimento = Estabelecimento(
        nome="Estabelecimento Login",
        login="estabelecimento.login",
        senha=hash_senha("senha123"),
        plano="basico",
        endereco="Rua A",
    )
    db_session.add(estabelecimento)
    db_session.commit()
    db_session.refresh(estabelecimento)

    sucesso = client.post("/auth/login", json={"usuario": "estabelecimento.login", "senha": "senha123"})
    assert sucesso.status_code == 200
    body = sucesso.json()
    assert body["is_admin"] is False
    assert body["tenant_id"] == estabelecimento.id
    assert body["tenant_name"] == estabelecimento.nome
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    invalido = client.post("/auth/login", json={"usuario": "estabelecimento.login", "senha": "errada"})
    assert invalido.status_code == 401


def test_auth_login_accepts_unique_email_local_part(client, db_session):
    estabelecimento = Estabelecimento(
        nome="Estabelecimento Alias",
        login="alias.unico@example.com",
        senha=hash_senha("senha123"),
        plano="basico",
        endereco="Rua Alias",
    )
    db_session.add(estabelecimento)
    db_session.commit()

    response = client.post("/auth/login", json={"usuario": "alias.unico", "senha": "senha123"})

    assert response.status_code == 200
    assert response.json()["tenant_id"] == estabelecimento.id


def test_auth_login_rejects_ambiguous_email_local_part(client, db_session):
    db_session.add_all(
        [
            Estabelecimento(
                nome="Alias Um",
                login="alias.duplicado@example.com",
                senha=hash_senha("senha123"),
                endereco="Rua Um",
            ),
            Estabelecimento(
                nome="Alias Dois",
                login="alias.duplicado@example.org",
                senha=hash_senha("senha123"),
                endereco="Rua Dois",
            ),
        ]
    )
    db_session.commit()

    response = client.post("/auth/login", json={"usuario": "alias.duplicado", "senha": "senha123"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Usuario ou senha invalidos."


def test_logout_invalida_token(client):
    resp_login = client.post(
        "/auth/login",
        json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA},
    )
    token = resp_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp_antes = client.get("/auth/me", headers=headers)
    assert resp_antes.status_code == 200

    resp_logout = client.post("/auth/logout", headers=headers)
    assert resp_logout.status_code == 200
    assert resp_logout.json()["detail"] == "Logout realizado com sucesso."

    resp_depois = client.get("/auth/me", headers=headers)
    assert resp_depois.status_code == 401


def test_logout_sem_token_retorna_401(client):
    resp = client.post("/auth/logout")
    assert resp.status_code == 401


def test_tenant_header_mismatch_retorna_403(client, dados_base, make_tenant_headers):
    token_tenant_correto = make_tenant_headers(dados_base["barbearia"].id)
    headers_mismatch = {
        **token_tenant_correto,
        "X-Barbearia-Id": str(dados_base["barbearia"].id + 999),
    }
    resp = client.get("/clientes/", headers=headers_mismatch)
    assert resp.status_code == 403


def test_me_retorna_dados_do_tenant(client, db_session, make_tenant_headers):
    b = Estabelecimento(
        nome="Tenant Me",
        login="tenant.me",
        senha=hash_senha("senha"),
        plano="premium",
        endereco="Rua Me",
    )
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)

    headers = make_tenant_headers(tenant_id=b.id)
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome"] == "Tenant Me"
    assert body["plano"] == "premium"
    assert body["is_admin"] is False
    assert "tipo_servico" in body


def test_me_admin_retorna_dados_admin(client):
    resp_login = client.post(
        "/auth/login",
        json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA},
    )
    token = resp_login.json()["access_token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_admin"] is True
    assert body["tipo_servico"] is None
