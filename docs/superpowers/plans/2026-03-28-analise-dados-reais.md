# Dados Reais na Aba Análise — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mock data in `AnaliseTab.tsx` with a real `GET /dashboard/{id}/analise` endpoint returning 5 analytics blocks for the current calendar month.

**Architecture:** Single new FastAPI endpoint + Pydantic schemas in the backend; new TypeScript types + `getDashboardAnalise()` function in the frontend; `AnaliseTab.tsx` replaces all `MOCK_*` constants with a `useEffect` API call.

**Tech Stack:** FastAPI + SQLAlchemy + pytest/SQLite (backend), Next.js 14 App Router + React hooks + TypeScript (frontend)

---

### Task 1: Add Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/dashboard.py`

- [ ] **Step 1: Append 6 new schemas**

Open `backend/app/schemas/dashboard.py` and append after the last existing class (`ClientesResponse`):

```python
class ResumoMes(BaseModel):
    agendamentos: int
    faturamento: float
    ticket_medio: float
    ocupacao: int           # 0–100 (percentual inteiro)


class DiaSemana(BaseModel):
    dia: str                # "Seg", "Ter", ..., "Dom"
    clientes: int


class HorarioCheio(BaseModel):
    hora: str               # "09:00", "18:00", etc.
    atendimentos: int


class ServicoAnalise(BaseModel):
    nome: str
    total: int


class ClientesAnalise(BaseModel):
    novos: int
    recorrentes: int
    cancelamentos: int
    no_show: int


class AnaliseResponse(BaseModel):
    resumo: ResumoMes
    semana: list[DiaSemana]
    horarios: list[HorarioCheio]
    servicos: list[ServicoAnalise]
    clientes: ClientesAnalise
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/dashboard.py
git commit -m "feat: add Pydantic schemas for /analise endpoint"
```

---

### Task 2: Backend endpoint (TDD)

**Files:**
- Modify: `backend/tests/conftest.py` (register dashboard router)
- Create: `backend/tests/test_analise_dashboard.py`
- Modify: `backend/app/routes/dashboard.py` (new endpoint + helper)

- [ ] **Step 1: Register dashboard router in conftest**

Open `backend/tests/conftest.py`.

Change the import on line 17:
```python
# Before:
from app.routes import agenda, agendamentos, chatbot, barbeiros, barbearia_funcionamento, clientes, servicos, whatsapp, barbearias, auth, webhooks, public, internal, webhook, estabelecimentos, profissionais, estabelecimento_funcionamento, configuracoes

# After:
from app.routes import agenda, agendamentos, chatbot, barbeiros, barbearia_funcionamento, clientes, servicos, whatsapp, barbearias, auth, webhooks, public, internal, webhook, estabelecimentos, profissionais, estabelecimento_funcionamento, configuracoes, dashboard
```

Add after `test_app.include_router(configuracoes.router)` (line 68):
```python
    test_app.include_router(dashboard.router)
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_analise_dashboard.py`:

```python
"""
Testes do endpoint GET /dashboard/{id}/analise
"""
from datetime import date, datetime, time, timedelta

import pytest

from app.models.agendamento import Agendamento
from app.models.cliente import Cliente
from app.models.estabelecimento import Estabelecimento
from app.models.profissional import Profissional
from app.models.servico import Servico


DIA_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


@pytest.fixture
def dados_analise(db_session):
    hoje = date.today()
    agora = datetime.now()
    inicio_mes = hoje.replace(day=1)

    est_a = Estabelecimento(nome="Est A", plano="premium")
    est_b = Estabelecimento(nome="Est B", plano="premium")
    est_c = Estabelecimento(nome="Est C Vazio", plano="premium")
    db_session.add_all([est_a, est_b, est_c])
    db_session.commit()
    db_session.refresh(est_a)
    db_session.refresh(est_b)
    db_session.refresh(est_c)

    prof_a = Profissional(nome="Prof A", barbearia_id=est_a.id)
    prof_b = Profissional(nome="Prof B", barbearia_id=est_b.id)
    db_session.add_all([prof_a, prof_b])
    db_session.commit()
    db_session.refresh(prof_a)
    db_session.refresh(prof_b)

    corte = Servico(nome="Corte", duracao_minutos=30, preco=40.0, barbearia_id=est_a.id)
    barba = Servico(nome="Barba", duracao_minutos=20, preco=30.0, barbearia_id=est_a.id)
    serv_b = Servico(nome="Corte B", duracao_minutos=30, preco=50.0, barbearia_id=est_b.id)
    db_session.add_all([corte, barba, serv_b])
    db_session.commit()
    db_session.refresh(corte)
    db_session.refresh(barba)
    db_session.refresh(serv_b)

    cli_a = Cliente(nome="Alice", telefone="111", estabelecimento_id=est_a.id)
    cli_b = Cliente(nome="Bob", telefone="222", estabelecimento_id=est_a.id)
    cli_c = Cliente(nome="Carol", telefone="333", estabelecimento_id=est_a.id)
    cli_b2 = Cliente(nome="Dave", telefone="999", estabelecimento_id=est_b.id)
    db_session.add_all([cli_a, cli_b, cli_c, cli_b2])
    db_session.commit()
    for c in [cli_a, cli_b, cli_c, cli_b2]:
        db_session.refresh(c)

    d1 = hoje  # garantido <= hoje nas queries do mês

    def _ag(est_id, prof_id, serv_id, cli_id, tel, nome, data, hora_h, hora_m, status):
        dt = datetime(data.year, data.month, data.day, hora_h, hora_m)
        return Agendamento(
            estabelecimento_id=est_id,
            profissional_id=prof_id,
            servico_id=serv_id,
            cliente_id=cli_id,
            cliente_nome=nome,
            cliente_telefone=tel,
            data=data,
            hora_inicio=time(hora_h, hora_m),
            data_hora_inicio=dt,
            data_hora_fim=dt + timedelta(hours=1),
            status=status,
        )

    # 4 confirmados: 3x Corte (Alice, Bob, Carol) + 1x Barba (Alice → recorrente)
    ag1 = _ag(est_a.id, prof_a.id, corte.id, cli_a.id, "111", "Alice", d1, 9, 0, "confirmado")
    ag2 = _ag(est_a.id, prof_a.id, corte.id, cli_b.id, "222", "Bob",   d1, 18, 0, "confirmado")
    ag3 = _ag(est_a.id, prof_a.id, corte.id, cli_c.id, "333", "Carol", d1, 18, 0, "confirmado")
    ag4 = _ag(est_a.id, prof_a.id, barba.id, cli_a.id, "111", "Alice", d1, 10, 0, "confirmado")
    # 1 cancelado
    ag5 = _ag(est_a.id, prof_a.id, corte.id, cli_b.id, "222", "Bob",   d1, 14, 0, "cancelado")
    # no-show: pendente com data_hora_inicio no passado (1º do mês às 00:01)
    dt_noshow = datetime(inicio_mes.year, inicio_mes.month, inicio_mes.day, 0, 1)
    ag6 = Agendamento(
        estabelecimento_id=est_a.id, profissional_id=prof_a.id,
        servico_id=corte.id, cliente_id=cli_b.id,
        cliente_nome="Bob", cliente_telefone="222",
        data=dt_noshow.date(), hora_inicio=time(0, 1),
        data_hora_inicio=dt_noshow, data_hora_fim=dt_noshow + timedelta(hours=1),
        status="pendente",
    )
    # pendente futuro: não é no-show
    dt_futuro = agora + timedelta(hours=2)
    ag7 = Agendamento(
        estabelecimento_id=est_a.id, profissional_id=prof_a.id,
        servico_id=corte.id, cliente_id=cli_a.id,
        cliente_nome="Alice", cliente_telefone="111",
        data=dt_futuro.date(), hora_inicio=time(dt_futuro.hour % 24, dt_futuro.minute),
        data_hora_inicio=dt_futuro, data_hora_fim=dt_futuro + timedelta(hours=1),
        status="pendente",
    )
    # est_b: 1 confirmado — não deve aparecer nos resultados de est_a
    ag_b = _ag(est_b.id, prof_b.id, serv_b.id, cli_b2.id, "999", "Dave", d1, 9, 0, "confirmado")

    db_session.add_all([ag1, ag2, ag3, ag4, ag5, ag6, ag7, ag_b])
    db_session.commit()

    return {"est_a": est_a, "est_b": est_b, "est_c": est_c, "d1": d1}


def _get(client, est_id, headers):
    return client.get(f"/dashboard/{est_id}/analise", headers=headers)


def test_resumo_agendamentos(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    assert resp.json()["resumo"]["agendamentos"] == 4


def test_resumo_faturamento(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    # 3 × R$40 + 1 × R$30 = R$150
    assert resp.json()["resumo"]["faturamento"] == pytest.approx(150.0)


def test_resumo_ticket_medio(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    # R$150 / 4 = R$37.50
    assert resp.json()["resumo"]["ticket_medio"] == pytest.approx(37.5)


def test_resumo_ocupacao(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    # confirmados=4, cancelados=1, no_show=1 → round(4/6*100) = 67
    assert resp.json()["resumo"]["ocupacao"] == 67


def test_semana_dia_e_contagem(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    d1 = dados_analise["d1"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    semana = resp.json()["semana"]
    # ag1, ag2, ag3, ag4 estão todos em d1 → 4 no dia da semana de d1
    expected_label = DIA_LABELS[d1.weekday()]
    dias = {item["dia"]: item["clientes"] for item in semana}
    assert dias[expected_label] == 4


def test_horarios_ordenados_por_volume(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    horarios = resp.json()["horarios"]
    # 18:00 tem 2 atendimentos (ag2 + ag3); os demais têm 1
    assert horarios[0]["hora"] == "18:00"
    assert horarios[0]["atendimentos"] == 2
    assert len(horarios) <= 5


def test_servicos_ordenados_por_total(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    servicos = resp.json()["servicos"]
    assert servicos[0]["nome"] == "Corte"
    assert servicos[0]["total"] == 3
    assert servicos[1]["nome"] == "Barba"
    assert servicos[1]["total"] == 1


def test_clientes_novos_e_recorrentes(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    clientes = resp.json()["clientes"]
    # Alice (111): ag1 + ag4 = 2 visitas → recorrente
    # Bob (222): ag2 = 1 visita → novo
    # Carol (333): ag3 = 1 visita → novo
    assert clientes["novos"] == 2
    assert clientes["recorrentes"] == 1


def test_clientes_cancelamentos(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    assert resp.json()["clientes"]["cancelamentos"] == 1


def test_clientes_no_show(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    # ag6: pendente com data_hora_inicio no passado → no-show
    # ag7: pendente com data_hora_inicio no futuro → não é no-show
    assert resp.json()["clientes"]["no_show"] == 1


def test_mes_vazio(client, dados_analise, make_tenant_headers):
    est_c = dados_analise["est_c"]
    resp = _get(client, est_c.id, make_tenant_headers(tenant_id=est_c.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["resumo"]["agendamentos"] == 0
    assert body["resumo"]["faturamento"] == 0.0
    assert body["resumo"]["ocupacao"] == 0
    assert body["semana"] == []
    assert body["horarios"] == []
    assert body["servicos"] == []
    assert body["clientes"]["novos"] == 0
    assert body["clientes"]["cancelamentos"] == 0
    assert body["clientes"]["no_show"] == 0


def test_tenant_isolamento(client, dados_analise, make_tenant_headers):
    est_a = dados_analise["est_a"]
    resp = _get(client, est_a.id, make_tenant_headers(tenant_id=est_a.id))
    assert resp.status_code == 200
    # est_b tem 1 agendamento (ag_b) — não deve aparecer
    assert resp.json()["resumo"]["agendamentos"] == 4


def test_403_tenant_errado(client, dados_analise, make_tenant_headers):
    est_a = dados_analise["est_a"]
    est_b = dados_analise["est_b"]
    # Token de est_a, mas tentando acessar endpoint de est_b
    headers = make_tenant_headers(tenant_id=est_a.id)
    resp = client.get(f"/dashboard/{est_b.id}/analise", headers=headers)
    assert resp.status_code == 403


def test_401_sem_token(client, dados_analise):
    est = dados_analise["est_a"]
    resp = client.get(f"/dashboard/{est.id}/analise")
    assert resp.status_code == 401


def test_403_plano_basico(client, db_session, make_tenant_headers):
    est_basico = Estabelecimento(nome="Básico", plano="basico")
    db_session.add(est_basico)
    db_session.commit()
    db_session.refresh(est_basico)
    headers = make_tenant_headers(tenant_id=est_basico.id)
    resp = client.get(f"/dashboard/{est_basico.id}/analise", headers=headers)
    assert resp.status_code == 403
```

- [ ] **Step 3: Run tests — verify they all fail**

```bash
cd backend && python -m pytest tests/test_analise_dashboard.py -v 2>&1 | head -25
```

Expected: All tests FAIL (404 — endpoint does not exist yet).

- [ ] **Step 4: Implement the endpoint**

Open `backend/app/routes/dashboard.py`.

**4a.** Change the `datetime` import line from:
```python
from datetime import date, timedelta
```
to:
```python
from datetime import date, datetime, timedelta
```

**4b.** Replace the `from app.schemas.dashboard import (...)` block with:
```python
from app.schemas.dashboard import (
    AnaliseResponse,
    ClientesAnalise,
    ClientesResponse,
    DiaSemana,
    FinanceiroResponse,
    HistoricoMes,
    HorarioCheio,
    ResumoMes,
    ServicoAnalise,
    ServicoMaisVendido,
    ServicosMaisVendidosResponse,
    TopCliente,
)
```

**4c.** Append at the end of the file:

```python
# Mapeamento: índice = Python weekday() (0=Seg, ..., 6=Dom)
_DIA_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


@router.get("/{barbearia_id}/analise", response_model=AnaliseResponse)
def analise(
    barbearia_id: int,
    tenant_id: int = Depends(verificar_plano_premium),
    db: Session = Depends(get_db),
):
    if barbearia_id != tenant_id:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    try:
        return _analise(db, tenant_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc


def _analise(db: Session, tenant_id: int) -> AnaliseResponse:
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)
    agora = datetime.now()

    # ── Resumo: confirmados no mês atual ──────────────────────────────────────
    row = (
        db.query(
            func.count(Agendamento.id).label("total"),
            func.coalesce(func.sum(Servico.preco), 0.0).label("fat"),
            func.coalesce(func.avg(Servico.preco), 0.0).label("ticket"),
        )
        .select_from(Agendamento)
        .join(Servico, Servico.id == Agendamento.servico_id)
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "confirmado",
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .first()
    )
    total_confirmados = int(row.total)
    faturamento = float(row.fat)
    ticket_medio = float(row.ticket)

    total_cancelados = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "cancelado",
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .scalar()
        or 0
    )

    total_no_show = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "pendente",
            Agendamento.data_hora_inicio < agora,
            Agendamento.data >= inicio_mes,
        )
        .scalar()
        or 0
    )

    total_demanda = total_confirmados + total_cancelados + total_no_show
    ocupacao = round(total_confirmados / total_demanda * 100) if total_demanda > 0 else 0

    resumo = ResumoMes(
        agendamentos=total_confirmados,
        faturamento=faturamento,
        ticket_medio=ticket_medio,
        ocupacao=ocupacao,
    )

    # ── Semana: confirmados agrupados por dia da semana ───────────────────────
    # extract("dow"): 0=Dom, 1=Seg, ..., 6=Sáb (PostgreSQL e SQLite via SQLAlchemy)
    dow_col = func.extract("dow", Agendamento.data).label("dow")
    semana_rows = (
        db.query(dow_col, func.count(Agendamento.id).label("total"))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "confirmado",
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .group_by(dow_col)
        .all()
    )
    contagem_semana = {int(r.dow): int(r.total) for r in semana_rows}
    # Ordem Seg→Dom; (dow-1)%7 converte SQL dow para índice de _DIA_LABELS
    semana = [
        DiaSemana(dia=_DIA_LABELS[(dow - 1) % 7], clientes=contagem_semana[dow])
        for dow in [1, 2, 3, 4, 5, 6, 0]
        if dow in contagem_semana
    ]

    # ── Horários mais cheios: top 5 ───────────────────────────────────────────
    hora_col = func.extract("hour", Agendamento.hora_inicio).label("hora")
    horario_rows = (
        db.query(hora_col, func.count(Agendamento.id).label("total"))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "confirmado",
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .group_by(hora_col)
        .order_by(func.count(Agendamento.id).desc())
        .limit(5)
        .all()
    )
    horarios = [
        HorarioCheio(hora=f"{int(r.hora):02d}:00", atendimentos=int(r.total))
        for r in horario_rows
    ]

    # ── Serviços mais vendidos: top 5 ─────────────────────────────────────────
    servico_rows = (
        db.query(Servico.nome, func.count(Agendamento.id).label("total"))
        .join(Agendamento, Agendamento.servico_id == Servico.id)
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "confirmado",
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .group_by(Servico.id, Servico.nome)
        .order_by(func.count(Agendamento.id).desc())
        .limit(5)
        .all()
    )
    servicos = [ServicoAnalise(nome=r.nome, total=int(r.total)) for r in servico_rows]

    # ── Clientes ──────────────────────────────────────────────────────────────
    freq_rows = (
        db.query(
            Agendamento.cliente_telefone,
            func.count(Agendamento.id).label("visitas"),
        )
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "confirmado",
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .group_by(Agendamento.cliente_telefone)
        .all()
    )
    novos = sum(1 for r in freq_rows if r.visitas == 1)
    recorrentes = sum(1 for r in freq_rows if r.visitas > 1)

    clientes = ClientesAnalise(
        novos=novos,
        recorrentes=recorrentes,
        cancelamentos=total_cancelados,
        no_show=total_no_show,
    )

    return AnaliseResponse(
        resumo=resumo,
        semana=semana,
        horarios=horarios,
        servicos=servicos,
        clientes=clientes,
    )
```

- [ ] **Step 5: Run tests — verify they all pass**

```bash
cd backend && python -m pytest tests/test_analise_dashboard.py -v
```

Expected: All 14 tests PASS.

- [ ] **Step 6: Run full test suite**

```bash
cd backend && python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 160+ passing, 0 failing.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/dashboard.py backend/tests/conftest.py backend/tests/test_analise_dashboard.py
git commit -m "feat: add GET /dashboard/{id}/analise endpoint with TDD"
```

---

### Task 3: Frontend types and API function

**Files:**
- Modify: `frontend/services/api.ts`

- [ ] **Step 1: Append types and function**

Open `frontend/services/api.ts`. After the closing `}` of `getDashboardClientes` (currently the last export in the file), append:

```typescript
// ─── DASHBOARD ANÁLISE ───────────────────────────────────────────────────────

export type ResumoMes = {
  agendamentos: number;
  faturamento: number;
  ticket_medio: number;
  ocupacao: number;
};

export type DiaSemana = {
  dia: string;
  clientes: number;
};

export type HorarioCheio = {
  hora: string;
  atendimentos: number;
};

export type ServicoAnalise = {
  nome: string;
  total: number;
};

export type ClientesAnalise = {
  novos: number;
  recorrentes: number;
  cancelamentos: number;
  no_show: number;
};

export type AnaliseResponse = {
  resumo: ResumoMes;
  semana: DiaSemana[];
  horarios: HorarioCheio[];
  servicos: ServicoAnalise[];
  clientes: ClientesAnalise;
};

export async function getDashboardAnalise(barbeariaId: string): Promise<AnaliseResponse> {
  const res = await apiFetch(`/dashboard/${barbeariaId}/analise`);
  return parseOrThrow(res, "Falha ao carregar dados de análise do dashboard.");
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: No output (clean).

- [ ] **Step 3: Commit**

```bash
git add frontend/services/api.ts
git commit -m "feat: add getDashboardAnalise() and TypeScript types for /analise"
```

---

### Task 4: Wire AnaliseTab with real data

**Files:**
- Modify: `frontend/app/dashboard/AnaliseTab.tsx`

- [ ] **Step 1: Replace file content**

Replace the entire content of `frontend/app/dashboard/AnaliseTab.tsx` with:

```tsx
"use client";

import { useEffect, useState } from "react";
import { BarChart2, DollarSign, Scissors, TrendingUp } from "lucide-react";
import { useAuthSession } from "@/services/auth";
import { getDashboardAnalise, type AnaliseResponse } from "@/services/api";
import styles from "./page.module.css";

const brl = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

export default function AnaliseTab() {
  const session = useAuthSession();
  const tenantId = session?.tenantId ?? "";

  const [data, setData] = useState<AnaliseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;
    getDashboardAnalise(tenantId)
      .then(setData)
      .catch(() => setError("Erro ao carregar análise."))
      .finally(() => setLoading(false));
  }, [tenantId]);

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.loadingPulse} />
        <p style={{ color: "var(--ink-muted)" }}>Carregando análise…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={styles.loadingState}>
        <p style={{ color: "var(--danger)" }}>{error ?? "Erro ao carregar análise."}</p>
      </div>
    );
  }

  const maxSemana = Math.max(...data.semana.map((d) => d.clientes), 1);
  const maxServico = data.servicos[0]?.total ?? 1;

  return (
    <div style={{ marginTop: "20px" }}>
      {/* Bloco 1 — Resumo do mês */}
      <div className={styles.statsGrid}>
        <article className={styles.statCard}>
          <div className={styles.statIcon}><Scissors size={22} /></div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Agendamentos</span>
            <strong className={styles.statValue}>{data.resumo.agendamentos}</strong>
            <span className={styles.statHelper}>no mês atual</span>
          </div>
        </article>

        <article className={styles.statCard}>
          <div className={styles.statIcon}><DollarSign size={22} /></div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Faturamento</span>
            <strong className={styles.statValue}>{brl(data.resumo.faturamento)}</strong>
            <span className={styles.statHelper}>no mês atual</span>
          </div>
        </article>

        <article className={styles.statCard}>
          <div className={styles.statIcon}><TrendingUp size={22} /></div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Ticket médio</span>
            <strong className={styles.statValue}>{brl(data.resumo.ticket_medio)}</strong>
            <span className={styles.statHelper}>por agendamento</span>
          </div>
        </article>

        <article className={styles.statCard}>
          <div className={styles.statIcon}><BarChart2 size={22} /></div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Taxa de ocupação</span>
            <strong className={styles.statValue}>{data.resumo.ocupacao}%</strong>
            <span className={styles.statHelper}>da agenda preenchida</span>
          </div>
        </article>
      </div>

      {/* Linha 2: Bloco 2 + Bloco 3 */}
      <div className={styles.analiseGrid3Col}>
        {/* Bloco 2 — Movimento da semana */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Movimento da semana</h2>
          <div className={styles.weekBarList}>
            {data.semana.map((item) => {
              const isPeak = item.clientes === maxSemana;
              return (
                <div key={item.dia} className={styles.weekBarItem}>
                  <span className={isPeak ? `${styles.weekBarLabel} ${styles.weekBarLabelPeak}` : styles.weekBarLabel}>
                    {item.dia}
                  </span>
                  <div className={styles.weekBarTrack}>
                    <div
                      className={isPeak ? `${styles.weekBarFill} ${styles.weekBarFillPeak}` : styles.weekBarFill}
                      style={{ width: `${(item.clientes / maxSemana) * 100}%` }}
                    />
                  </div>
                  <span className={isPeak ? `${styles.weekBarCount} ${styles.weekBarCountPeak}` : styles.weekBarCount}>
                    {item.clientes}
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        {/* Bloco 3 — Horários mais cheios */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Horários mais cheios</h2>
          <div className={styles.rankList}>
            {data.horarios.map((item, i) => {
              const isTop = i === 0;
              return (
                <div key={item.hora} className={isTop ? `${styles.rankItem} ${styles.rankItemTop}` : styles.rankItem}>
                  <span className={isTop ? `${styles.rankPos} ${styles.rankPosTop}` : styles.rankPos}>
                    #{i + 1}
                  </span>
                  <span className={styles.rankLabel}>{item.hora}</span>
                  <span className={isTop ? `${styles.rankCount} ${styles.rankCountTop}` : styles.rankCount}>
                    {item.atendimentos} atend.
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* Linha 3: Bloco 4 + Bloco 5 */}
      <div className={styles.analiseGrid2Col}>
        {/* Bloco 4 — Serviços mais vendidos */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Serviços mais vendidos</h2>
          <div className={styles.servicosList}>
            {data.servicos.map((s) => (
              <div key={s.nome} className={styles.servicoItem}>
                <div className={styles.servicoHeader}>
                  <span className={styles.servicoNome}>{s.nome}</span>
                  <span className={styles.servicoVendas}>{s.total}×</span>
                </div>
                <div className={styles.progressTrack}>
                  <div
                    className={styles.progressBar}
                    style={{ width: `${(s.total / maxServico) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Bloco 5 — Clientes & Retenção */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Clientes & Retenção</h2>
          <div className={styles.clienteStats} style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{data.clientes.novos}</strong>
              <span className={styles.clienteStatLabel}>Novos</span>
            </div>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{data.clientes.recorrentes}</strong>
              <span className={styles.clienteStatLabel}>Recorrentes</span>
            </div>
          </div>
          <hr className={styles.metricDivider} />
          <div className={styles.clienteStats} style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
            <div className={`${styles.clienteStatItem} ${styles.clienteStatItemDanger}`}>
              <strong className={`${styles.clienteStatValue} ${styles.clienteStatValueDanger}`}>
                {data.clientes.cancelamentos}
              </strong>
              <span className={`${styles.clienteStatLabel} ${styles.clienteStatLabelDanger}`}>
                Cancelamentos
              </span>
            </div>
            <div className={`${styles.clienteStatItem} ${styles.clienteStatItemDanger}`}>
              <strong className={`${styles.clienteStatValue} ${styles.clienteStatValueDanger}`}>
                {data.clientes.no_show}
              </strong>
              <span className={`${styles.clienteStatLabel} ${styles.clienteStatLabelDanger}`}>
                Faltas (no-show)
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: No output (clean).

- [ ] **Step 3: Run backend tests one final time**

```bash
cd backend && python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/dashboard/AnaliseTab.tsx
git commit -m "feat: wire AnaliseTab to real API — remove all mock data"
```
