def test_processar_reminders_sem_token_configurado(client, monkeypatch):
    """Quando INTERNAL_REMINDER_TOKEN não está setado, qualquer requisição passa."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("INTERNAL_REMINDER_TOKEN", raising=False)

    resp = client.post("/internal/reminders/process")
    assert resp.status_code == 503


def test_processar_reminders_token_invalido(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_REMINDER_TOKEN", "secret123")
    resp = client.post(
        "/internal/reminders/process",
        headers={"X-Internal-Token": "errado"},
    )
    assert resp.status_code == 401


def test_processar_reminders_token_valido(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_REMINDER_TOKEN", "secret123")
    resp = client.post(
        "/internal/reminders/process",
        headers={"X-Internal-Token": "secret123"},
    )
    assert resp.status_code == 200


def test_expirar_pagamentos_pendentes_exige_token_em_producao(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("INTERNAL_REMINDER_TOKEN", raising=False)

    resp = client.post("/internal/payments/expire-pending")

    assert resp.status_code == 401
