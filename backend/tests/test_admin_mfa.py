import pyotp

import app.routes.auth as auth_module
from app.models.admin_mfa import AdminMfaSetting


def _login_admin(client):
    return client.post(
        "/auth/login",
        json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA},
    )


def test_admin_mfa_requires_second_factor_after_activation(client, db_session):
    initial_login = _login_admin(client)
    assert initial_login.status_code == 200
    assert initial_login.json()["mfa_required"] is False
    assert initial_login.json()["mfa_setup_required"] is True
    assert client.get("/estabelecimentos/").status_code == 403

    setup = client.post("/auth/admin/mfa/setup", json={"senha": auth_module.ADMIN_SENHA})
    assert setup.status_code == 200
    secret = setup.json()["manual_key"]
    repeated_setup = client.post("/auth/admin/mfa/setup", json={"senha": auth_module.ADMIN_SENHA})
    assert repeated_setup.status_code == 200
    assert repeated_setup.json()["manual_key"] == secret
    stored = db_session.get(AdminMfaSetting, auth_module.ADMIN_USUARIO)
    assert stored.pending_secret_encrypted
    assert secret not in stored.pending_secret_encrypted

    confirm = client.post("/auth/admin/mfa/setup/confirm", json={"code": pyotp.TOTP(secret).now()})
    assert confirm.status_code == 200
    recovery_codes = confirm.json()["recovery_codes"]
    assert len(recovery_codes) == 10
    assert all("-" in code for code in recovery_codes)

    client.post("/auth/logout")
    pending = _login_admin(client)
    assert pending.status_code == 200
    assert pending.json()["mfa_required"] is True
    assert pending.json()["access_token"] is None

    invalid = client.post(
        "/auth/admin/mfa/verify",
        json={"challenge": pending.json()["mfa_challenge"], "code": "000000"},
    )
    assert invalid.status_code == 401

    verified = client.post(
        "/auth/admin/mfa/verify",
        json={"challenge": pending.json()["mfa_challenge"], "code": pyotp.TOTP(secret).now()},
    )
    assert verified.status_code == 200
    assert verified.json()["is_admin"] is True


def test_admin_mfa_recovery_code_is_single_use(client):
    _login_admin(client)
    setup = client.post("/auth/admin/mfa/setup", json={"senha": auth_module.ADMIN_SENHA})
    secret = setup.json()["manual_key"]
    recovery_codes = client.post(
        "/auth/admin/mfa/setup/confirm",
        json={"code": pyotp.TOTP(secret).now()},
    ).json()["recovery_codes"]
    client.post("/auth/logout")

    first_login = _login_admin(client).json()
    first = client.post(
        "/auth/admin/mfa/verify",
        json={"challenge": first_login["mfa_challenge"], "code": recovery_codes[0]},
    )
    assert first.status_code == 200
    client.post("/auth/logout")

    second_login = _login_admin(client).json()
    reused = client.post(
        "/auth/admin/mfa/verify",
        json={"challenge": second_login["mfa_challenge"], "code": recovery_codes[0]},
    )
    assert reused.status_code == 401
