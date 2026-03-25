def test_processar_reminders_sem_token_configurado(client):
    """Quando INTERNAL_REMINDER_TOKEN não está setado, qualquer requisição passa."""
    resp = client.post("/internal/reminders/process")
    assert resp.status_code == 200


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
