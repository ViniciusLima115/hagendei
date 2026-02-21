def test_barbeiros_criar_e_listar(client):
    criar = client.post("/barbeiros/", json={"nome": "Carlos"})
    assert criar.status_code == 200
    assert criar.json()["nome"] == "Carlos"

    listar = client.get("/barbeiros/")
    assert listar.status_code == 200
    body = listar.json()
    assert len(body) == 1
    assert body[0]["nome"] == "Carlos"


def test_servicos_criar_e_listar(client):
    criar = client.post(
        "/servicos/",
        json={"nome": "Barba", "duracao_minutos": 30, "preco": 25.0},
    )
    assert criar.status_code == 200
    assert criar.json()["nome"] == "Barba"

    listar = client.get("/servicos/")
    assert listar.status_code == 200
    body = listar.json()
    assert len(body) == 1
    assert body[0]["duracao_minutos"] == 30


def test_clientes_criar_listar_e_duplicado(client):
    criar = client.post(
        "/clientes/",
        json={"telefone": "5582980000000", "nome": "Cliente A"},
    )
    assert criar.status_code == 200
    assert criar.json()["telefone"] == "5582980000000"

    duplicado = client.post(
        "/clientes/",
        json={"telefone": "5582980000000", "nome": "Cliente B"},
    )
    assert duplicado.status_code == 400
    assert duplicado.json()["detail"] == "Telefone já cadastrado"

    listar = client.get("/clientes/")
    assert listar.status_code == 200
    body = listar.json()
    assert len(body) == 1
    assert body[0]["nome"] == "Cliente A"
