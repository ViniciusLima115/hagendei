# Rebrand Barbershop → Hagendei Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish renaming every "barbearia"/"barbershop" identifier, API contract, test, and UI/doc reference to the "estabelecimento"/"Hagendei" vocabulary already adopted by the newer parts of the codebase, then rebrand the visible product name and the GitHub repository.

**Architecture:** No new architecture — this is a rename/cleanup pass. Almost everywhere in the backend, a canonical `Estabelecimento`-named implementation already exists with a `Barbearia`-named legacy layer on top (shim modules, ORM synonyms, back-compat aliases, or byte-identical duplicate files). The strategy is: for each pair, keep the canonical implementation, repoint every remaining consumer to it, delete the legacy layer, and verify with the existing test suite. A few pieces (an HTTP header name and two public URL paths) are a real API contract shared by frontend and backend and must be renamed atomically in the same commit.

**Tech Stack:** FastAPI + SQLAlchemy + pytest (backend), Next.js 16 / React 19 + TypeScript (frontend), gh CLI (GitHub repo rename).

**Read this first — reconciliation map** (the non-obvious "which side wins" decisions this plan makes):

| Legacy (to remove) | Canonical (keep) | Why |
|---|---|---|
| `backend/app/models/barbearia.py` (`Barbearia = Estabelecimento` shim) | `backend/app/models/estabelecimento.py` | Shim's own comment says "será removido na Tarefa 17" |
| `backend/app/schemas/barbearia.py` (`Barbearia*` classes, with `Estabelecimento* = Barbearia*` aliases at the bottom) | New `backend/app/schemas/estabelecimento.py` (classes renamed, no aliases) | Same pattern as models |
| `backend/app/services/barbershop_hours_service.py` | `backend/app/services/estabelecimento_hours_service.py` — **but its content is replaced by `barbershop_hours_service.py`'s logic**, not kept as-is | `barbershop_hours_service.py` is actually the newer/superset version (supports per-establishment `intervalo_minutos`); `estabelecimento_hours_service.py` is the outdated duplicate. Confirmed via diff. |
| `backend/app/routes/barbearias.py`, `backend/app/routes/barbearia_funcionamento.py` | `backend/app/routes/estabelecimentos.py`, `backend/app/routes/estabelecimento_funcionamento.py` | Confirmed via the graph tool: the legacy files have **zero importers** and are **not registered in `main.py`** — dead in production. They're only kept alive by `tests/conftest.py`'s test app fixture, which wires up both old and new routers. |
| `backend/tests/test_barbearia_funcionamento.py`, `backend/tests/test_auth_barbearias.py` | Coverage ported into `test_estabelecimento_funcionamento.py` / new `test_estabelecimentos_admin.py` / new `test_auth.py` | These files test real business logic (booking-blocked-outside-hours, admin CRUD) that has **no other coverage** — `test_estabelecimento_funcionamento.py` only covers GET/PUT, not the slot-blocking or CRUD behavior. Deleting them outright would create a coverage gap on live code. |
| `Servico.barbearia_id` / `Cliente.barbearia_id` / `Agendamento.barbearia_id` (SQLAlchemy `synonym("estabelecimento_id")`) | `estabelecimento_id` (the real column) | Synonym is a deliberate legacy alias, safe to remove once every consumer uses `estabelecimento_id` — same column underneath. |
| `Agendamento.barbearia` (`relationship(..., overlaps="estabelecimento")`) | `Agendamento.estabelecimento` | Same relationship, two names. |
| `frontend/services/barbershops-admin.ts` | `frontend/services/estabelecimentos-admin.ts` | Confirmed **zero importers** anywhere in `frontend/app` — fully dead. `estabelecimentos-admin.ts` is the superset (has payment-account functions the old file never got) and is the only one imported by `admin/master/page.tsx`, via its own `Barbearia*` back-compat aliases. |

**Cross-cutting API contract note:** the HTTP header `X-Barbearia-Id` and the URL paths `/public/barbearia/{slug}` and `/public/barbearia-id/{id}` are called directly by the frontend (`frontend/services/api.ts`). Renaming them is a real contract change — Task 5 changes both backend and frontend in the same commit so there's never a broken intermediate state.

**Explicitly out of scope (do not touch):** `Estabelecimento.tipo_servico` server default value `"barbearia"` (a business-data value, not a code identifier — flagged during brainstorming, user did not approve changing it), Alembic migration history files under `backend/alembic/versions/` (never rewrite historical migrations), and anything under `.claude/worktrees/` (stale worktree copies, not part of the working tree).

---

## Backend

### Task 1: Reconcile schemas — `barbearia.py` → `estabelecimento.py`

**Files:**
- Create: `backend/app/schemas/estabelecimento.py`
- Delete: `backend/app/schemas/barbearia.py`
- Modify: `backend/app/schemas/barbeiro.py:3`, `backend/app/routes/estabelecimento_funcionamento.py:7`, `backend/app/routes/estabelecimentos.py:12`
- Modify (deleted in Task 3, but must still import correctly until then): `backend/app/routes/barbearia_funcionamento.py`, `backend/app/routes/barbearias.py`

- [ ] **Step 1: Create the new schema file with canonical names (no aliases)**

Write `backend/app/schemas/estabelecimento.py` as the current `backend/app/schemas/barbearia.py` with every `Barbearia`-prefixed name renamed and the compatibility aliases at the bottom removed:

```python
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PlanoEstabelecimento = Literal["basico", "premium"]
StatusManualEstabelecimento = Literal["ativo", "inativo"]


class EstabelecimentoAdminCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    login: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9._@+-]+$")
    senha: str = Field(min_length=8, max_length=128)
    plano: PlanoEstabelecimento = "basico"
    status_manual: StatusManualEstabelecimento = "ativo"
    vencimento_em: date
    trial_ativo: bool = False
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    endereco: str = Field(default="", max_length=255)

    @field_validator("senha")
    @classmethod
    def validar_tamanho_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("A senha deve ter no maximo 72 bytes.")
        return value


class EstabelecimentoAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    login: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9._@+-]+$")
    senha: str = Field(min_length=8, max_length=128)
    plano: PlanoEstabelecimento
    status_manual: StatusManualEstabelecimento
    vencimento_em: date
    trial_ativo: bool
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    endereco: str = Field(default="", max_length=255)

    @field_validator("senha")
    @classmethod
    def validar_tamanho_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("A senha deve ter no maximo 72 bytes.")
        return value


class EstabelecimentoAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    slug: str | None = None
    login: str | None = None
    senha: str | None = Field(default=None, exclude=True)
    plano: PlanoEstabelecimento | None = "basico"
    status_manual: StatusManualEstabelecimento | None = "ativo"
    vencimento_em: date | None = None
    trial_ativo: bool = False
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    criado_em: datetime


class EstabelecimentoFuncionamentoDia(BaseModel):
    ativo: bool = True
    inicio: str = "08:00"
    fim: str = "18:00"

    @field_validator("inicio", "fim")
    @classmethod
    def validar_hora(cls, value: str) -> str:
        texto = value.strip()
        try:
            datetime.strptime(texto, "%H:%M")
        except ValueError as exc:
            raise ValueError("Horario deve estar no formato HH:MM.") from exc
        return texto


class EstabelecimentoFuncionamento(BaseModel):
    seg: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    ter: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    qua: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    qui: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    sex: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    sab: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    dom: EstabelecimentoFuncionamentoDia = EstabelecimentoFuncionamentoDia()
    intervalo_minutos: int | None = None  # 5–120, step 5

    @model_validator(mode="after")
    def validar_intervalos(self):
        for dia in ("seg", "ter", "qua", "qui", "sex", "sab", "dom"):
            item = getattr(self, dia)
            if item.ativo and item.inicio >= item.fim:
                raise ValueError(f"{dia}: horario inicial precisa ser menor que o final.")
        return self
```

- [ ] **Step 2: Delete the old schema file**

```bash
git rm backend/app/schemas/barbearia.py
```

- [ ] **Step 3: Update the 3 surviving importers**

In `backend/app/schemas/barbeiro.py:3`, `backend/app/routes/estabelecimento_funcionamento.py:7`, `backend/app/routes/estabelecimentos.py:12`, replace the import and every use of the old names:

```bash
for f in backend/app/schemas/barbeiro.py backend/app/routes/estabelecimento_funcionamento.py backend/app/routes/estabelecimentos.py; do
  perl -pi -e 's/from app\.schemas\.barbearia import/from app.schemas.estabelecimento import/' "$f"
  perl -pi -e 's/\bBarbeariaAdminCreate\b/EstabelecimentoAdminCreate/g;
               s/\bBarbeariaAdminUpdate\b/EstabelecimentoAdminUpdate/g;
               s/\bBarbeariaAdminResponse\b/EstabelecimentoAdminResponse/g;
               s/\bBarbeariaFuncionamentoDia\b/EstabelecimentoFuncionamentoDia/g;
               s/\bBarbeariaFuncionamento\b/EstabelecimentoFuncionamento/g;' "$f"
done
```

Note: `backend/app/routes/barbearias.py` and `backend/app/routes/barbearia_funcionamento.py` also import from `app.schemas.barbearia` — leave them broken for now, they're deleted whole in Task 3 (do Task 3 right after this one, don't run the app in between).

- [ ] **Step 4: Verify no remaining references to the old schema names outside deleted-in-Task-3 files**

```bash
grep -rn "schemas\.barbearia\|BarbeariaAdminCreate\|BarbeariaAdminUpdate\|BarbeariaAdminResponse\|BarbeariaFuncionamento" backend/app --include="*.py" | grep -v __pycache__ | grep -v "app/routes/barbearias.py" | grep -v "app/routes/barbearia_funcionamento.py"
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/estabelecimento.py backend/app/schemas/barbeiro.py backend/app/routes/estabelecimento_funcionamento.py backend/app/routes/estabelecimentos.py
git commit -m "refactor(schemas): renomear schemas/barbearia.py para schemas/estabelecimento.py"
```

---

### Task 2: Reconcile hours service — keep the superset logic

**Files:**
- Modify: `backend/app/services/estabelecimento_hours_service.py` (replace content)
- Delete: `backend/app/services/barbershop_hours_service.py`
- Modify: `backend/app/routes/agenda.py`, `backend/app/routes/barbeiros.py`, `backend/app/services/agenda_service.py`, `backend/app/services/agendamento_service.py`, `backend/app/services/public_booking_service.py`
- Modify (deleted in Task 3): `backend/app/routes/barbearia_funcionamento.py`

- [ ] **Step 1: Replace `estabelecimento_hours_service.py` with the superset logic (param renamed)**

```python
from datetime import date, datetime, time, timedelta

from app.config import HORARIO_ABERTURA, HORARIO_FECHAMENTO, INTERVALO_MINUTOS


DAY_KEYS = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")
WEEKDAY_TO_KEY = {
    0: "seg",
    1: "ter",
    2: "qua",
    3: "qui",
    4: "sex",
    5: "sab",
    6: "dom",
}


def default_working_hours() -> dict[str, dict[str, str | bool]]:
    inicio = f"{HORARIO_ABERTURA:02d}:00"
    fim = f"{HORARIO_FECHAMENTO:02d}:00"
    return {
        key: {
            "ativo": True,
            "inicio": inicio,
            "fim": fim,
        }
        for key in DAY_KEYS
    }


def _clone_working_hours(data: dict[str, dict[str, str | bool]]) -> dict[str, dict[str, str | bool]]:
    return {
        key: {
            "ativo": bool(value["ativo"]),
            "inicio": str(value["inicio"]),
            "fim": str(value["fim"]),
        }
        for key, value in data.items()
    }


def _parse_time(value: str, fallback: str) -> str:
    text = (value or "").strip()
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        return fallback
    return text


def normalize_working_hours(
    raw: dict | None,
    *,
    fallback: dict[str, dict[str, str | bool]] | None = None,
) -> dict[str, dict[str, str | bool]]:
    normalized = _clone_working_hours(fallback or default_working_hours())
    if not isinstance(raw, dict):
        return normalized

    for key in DAY_KEYS:
        data = raw.get(key)
        if not isinstance(data, dict):
            continue
        normalized[key] = {
            "ativo": bool(data.get("ativo", normalized[key]["ativo"])),
            "inicio": _parse_time(str(data.get("inicio", normalized[key]["inicio"])), str(normalized[key]["inicio"])),
            "fim": _parse_time(str(data.get("fim", normalized[key]["fim"])), str(normalized[key]["fim"])),
        }

    return normalized


def get_working_hours(estabelecimento) -> dict[str, dict[str, str | bool]]:
    return normalize_working_hours(getattr(estabelecimento, "horarios_funcionamento", None))


def get_barbeiro_working_hours(estabelecimento, barbeiro) -> dict[str, dict[str, str | bool]]:
    base_schedule = get_working_hours(estabelecimento)
    raw = getattr(barbeiro, "horarios_funcionamento", None)
    if raw is None:
        return base_schedule
    return normalize_working_hours(raw, fallback=base_schedule)


def _get_window_from_schedule(
    schedule: dict[str, dict[str, str | bool]],
    target_date: date,
) -> tuple[time, time] | None:
    key = WEEKDAY_TO_KEY[target_date.weekday()]
    day = schedule[key]
    if not day["ativo"]:
        return None
    start = datetime.strptime(str(day["inicio"]), "%H:%M").time()
    end = datetime.strptime(str(day["fim"]), "%H:%M").time()
    if start >= end:
        return None
    return start, end


def get_working_window(estabelecimento, target_date: date, barbeiro=None) -> tuple[time, time] | None:
    base_schedule = get_working_hours(estabelecimento)
    base_window = _get_window_from_schedule(base_schedule, target_date)
    if not base_window:
        return None

    if barbeiro is None:
        return base_window

    barbeiro_window = _get_window_from_schedule(
        get_barbeiro_working_hours(estabelecimento, barbeiro),
        target_date,
    )
    if not barbeiro_window:
        return None

    start = max(base_window[0], barbeiro_window[0])
    end = min(base_window[1], barbeiro_window[1])
    if start >= end:
        return None
    return start, end


def build_day_slots(
    estabelecimento,
    target_date: date,
    duration_minutes: int,
    barbeiro=None,
    interval_minutes: int | None = None,
) -> list[datetime]:
    """
    Gera lista de slots disponíveis no dia.

    Args:
        duration_minutes: duração do serviço — usado para checar se o slot cabe antes do fim.
        interval_minutes: passo entre slots. Se None, lê de estabelecimento.intervalo_minutos,
                          com fallback para INTERVALO_MINUTOS global.
    """
    window = get_working_window(estabelecimento, target_date, barbeiro=barbeiro)
    if not window:
        return []

    if interval_minutes is None:
        interval_minutes = getattr(estabelecimento, "intervalo_minutos", None) or INTERVALO_MINUTOS

    start, end = window
    current = datetime.combine(target_date, start)
    finish = datetime.combine(target_date, end)
    slots: list[datetime] = []

    while current + timedelta(minutes=duration_minutes) <= finish:
        slots.append(current)
        current += timedelta(minutes=interval_minutes)

    return slots


def is_within_working_hours(estabelecimento, start_at: datetime, end_at: datetime, barbeiro=None) -> bool:
    window = get_working_window(estabelecimento, start_at.date(), barbeiro=barbeiro)
    if not window or start_at.date() != end_at.date():
        return False

    start, end = window
    day_start = datetime.combine(start_at.date(), start)
    day_end = datetime.combine(start_at.date(), end)
    return day_start <= start_at and end_at <= day_end
```

- [ ] **Step 2: Delete the old service file**

```bash
git rm backend/app/services/barbershop_hours_service.py
```

- [ ] **Step 3: Repoint the 5 surviving importers**

Function names are unchanged (`default_working_hours`, `get_working_hours`, `get_barbeiro_working_hours`, `get_working_window`, `build_day_slots`, `is_within_working_hours`, `normalize_working_hours`), only the module path changes:

```bash
for f in backend/app/routes/agenda.py backend/app/routes/barbeiros.py backend/app/services/agenda_service.py backend/app/services/agendamento_service.py backend/app/services/public_booking_service.py; do
  perl -pi -e 's/from app\.services\.barbershop_hours_service import/from app.services.estabelecimento_hours_service import/' "$f"
done
```

Note: `backend/app/routes/barbearia_funcionamento.py` also imports from `barbershop_hours_service` — it's deleted whole in Task 3, leave it for now.

- [ ] **Step 4: Verify**

```bash
grep -rn "barbershop_hours_service" backend/app --include="*.py" | grep -v __pycache__ | grep -v "app/routes/barbearia_funcionamento.py"
```

Expected: no output.

- [ ] **Step 5: Run the affected test files**

```bash
cd backend && python -m pytest tests/test_estabelecimento_hours.py tests/test_scheduler.py -v
```

Expected: PASS (these exercise `build_day_slots`/`get_working_window` directly or indirectly).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/estabelecimento_hours_service.py backend/app/routes/agenda.py backend/app/routes/barbeiros.py backend/app/services/agenda_service.py backend/app/services/agendamento_service.py backend/app/services/public_booking_service.py
git commit -m "refactor(services): unificar barbershop_hours_service em estabelecimento_hours_service (mantendo suporte a intervalo_minutos por estabelecimento)"
```

---

### Task 3: Delete dead routers and fix the test app fixture

**Files:**
- Delete: `backend/app/routes/barbearias.py`, `backend/app/routes/barbearia_funcionamento.py`
- Modify: `backend/tests/conftest.py:30` (import line), `backend/tests/conftest.py:80,82` (`test_app.include_router` calls)

- [ ] **Step 1: Confirm these routers are genuinely unused in `main.py` (already verified, re-confirm before deleting)**

```bash
grep -n "barbearias\.\|barbearia_funcionamento\." backend/app/main.py
```

Expected: no output — `main.py` only registers `estabelecimentos.router` and `estabelecimento_funcionamento.router`.

- [ ] **Step 2: Delete the dead route files**

```bash
git rm backend/app/routes/barbearias.py backend/app/routes/barbearia_funcionamento.py
```

- [ ] **Step 3: Remove them from the test app fixture**

In `backend/tests/conftest.py`, remove `barbearia_funcionamento` and `barbearias` from the import line (currently line 30):

```python
from app.routes import agenda, agendamentos, chatbot, barbeiros, clientes, servicos, whatsapp, auth, webhooks, public, internal, webhook, estabelecimentos, profissionais, estabelecimento_funcionamento, configuracoes, dashboard, notificacoes, integrations, payments
```

Remove these two lines from the `app` fixture (currently lines 80 and 82):

```python
    test_app.include_router(barbearia_funcionamento.router)
    test_app.include_router(barbearias.router)
```

- [ ] **Step 4: Verify the test app now matches `main.py`'s router list**

```bash
diff <(grep -oP '(?<=app\.include_router\()\w+' backend/app/main.py | sort) <(grep -oP '(?<=test_app\.include_router\()\w+' backend/tests/conftest.py | sort)
```

Expected: no output (identical router lists).

- [ ] **Step 5: Run the full suite (Task 4 will fix the now-broken tests that hit `/barbearias/*`)**

```bash
cd backend && python -m pytest -q 2>&1 | tail -30
```

Expected: `test_barbearia_funcionamento.py` and `test_auth_barbearias.py` fail with 404s (routes gone) — that's expected, Task 4 fixes them. No *other* test file should newly fail.

- [ ] **Step 6: Commit**

```bash
git add -A backend/app/routes backend/tests/conftest.py
git commit -m "refactor(routes): remover barbearias.py e barbearia_funcionamento.py (rotas mortas, nao registradas em main.py)"
```

---

### Task 4: Port test coverage, delete legacy test files

**Files:**
- Modify: `backend/tests/test_estabelecimento_funcionamento.py` (add 3 ported tests)
- Create: `backend/tests/test_estabelecimentos_admin.py` (ported CRUD tests)
- Create: `backend/tests/test_auth.py` (ported generic auth tests)
- Delete: `backend/tests/test_barbearia_funcionamento.py`, `backend/tests/test_auth_barbearias.py`

- [ ] **Step 1: Read the current `test_estabelecimento_funcionamento.py` to append to it correctly**

```bash
cat backend/tests/test_estabelecimento_funcionamento.py
```

- [ ] **Step 2: Append the 3 tests from `test_barbearia_funcionamento.py` that have no equivalent coverage**

Append to `backend/tests/test_estabelecimento_funcionamento.py` (adjust imports at the top of the file to add `from datetime import datetime, timedelta` and `from app.models.barbeiro import Barbeiro` / `from app.models.servico import Servico` / `from app.models.estabelecimento import Estabelecimento` if not already present):

```python
def _funcionamento_seg_a_sab():
    return {
        "seg": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "ter": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qua": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qui": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sex": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sab": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "dom": {"ativo": False, "inicio": "08:00", "fim": "18:00"},
    }


def _proximo_dia_semana(target_weekday: int) -> datetime:
    now = datetime.now()
    delta = (target_weekday - now.weekday()) % 7
    if delta == 0:
        delta = 7
    return now + timedelta(days=delta)


def test_tenant_pode_salvar_funcionamento(client, dados_base, tenant_headers, db_session):
    payload = _funcionamento_seg_a_sab()

    resp = client.put("/estabelecimentos/me/funcionamento", json=payload, headers=tenant_headers)
    assert resp.status_code == 200
    assert resp.json()["dom"]["ativo"] is False
    assert resp.json()["seg"]["inicio"] == "08:00"

    db_session.refresh(dados_base["estabelecimento"])
    assert dados_base["estabelecimento"].horarios_funcionamento["sab"]["fim"] == "18:00"


def test_horarios_publicos_respeitam_dia_fechado(client, db_session):
    estabelecimento = Estabelecimento(
        nome="Estabelecimento Horarios",
        slug="estabelecimento-horarios",
        horarios_funcionamento=_funcionamento_seg_a_sab(),
    )
    db_session.add(estabelecimento)
    db_session.commit()
    db_session.refresh(estabelecimento)

    domingo = _proximo_dia_semana(6)
    resp = client.get(
        f"/public/estabelecimento-id/{estabelecimento.id}",
        params={"data": domingo.date().isoformat()},
    )
    assert resp.status_code == 200


def test_agendamento_bloqueia_horario_fora_do_funcionamento(client, dados_base, tenant_headers, db_session):
    payload = _funcionamento_seg_a_sab()
    resp_put = client.put("/estabelecimentos/me/funcionamento", json=payload, headers=tenant_headers)
    assert resp_put.status_code == 200

    servico = db_session.query(Servico).filter(Servico.estabelecimento_id == dados_base["estabelecimento"].id).first()
    domingo = _proximo_dia_semana(6)
    inicio = domingo.replace(hour=10, minute=0, second=0, microsecond=0)

    resp = client.post(
        "/agendamentos/",
        json={
            "cliente_nome": "Cliente Teste",
            "cliente_telefone": "11999999999",
            "servico_id": servico.id,
            "inicio": inicio.isoformat(),
        },
        headers=tenant_headers,
    )
    assert resp.status_code in (400, 422)


def test_agendamento_bloqueia_horario_fora_do_funcionamento_do_barbeiro(
    client, dados_base, tenant_headers, db_session
):
    barbeiro = db_session.query(Barbeiro).filter(
        Barbeiro.estabelecimento_id == dados_base["estabelecimento"].id
    ).first()
    barbeiro.horarios_funcionamento = {
        **_funcionamento_seg_a_sab(),
        "seg": {"ativo": False, "inicio": "08:00", "fim": "18:00"},
    }
    db_session.commit()

    servico = db_session.query(Servico).filter(Servico.estabelecimento_id == dados_base["estabelecimento"].id).first()
    segunda = _proximo_dia_semana(0)
    inicio = segunda.replace(hour=10, minute=0, second=0, microsecond=0)

    resp = client.post(
        "/agendamentos/",
        json={
            "cliente_nome": "Cliente Teste",
            "cliente_telefone": "11999999999",
            "servico_id": servico.id,
            "barbeiro_id": barbeiro.id,
            "inicio": inicio.isoformat(),
        },
        headers=tenant_headers,
    )
    assert resp.status_code in (400, 422)
```

**Important:** the original tests used `dados_base["barbearia"]` (the `dados_base` fixture in `conftest.py` — check its exact key name; it may already be `dados_base["estabelecimento"]` after Task 6's sweep, or still `dados_base["barbearia"]` if `conftest.py` hasn't been touched yet). Run `grep -n '"barbearia"\|"estabelecimento"' backend/tests/conftest.py` before writing this step and use whichever key the fixture actually returns at this point in the plan (Task 6 renames it — if Task 6 hasn't run yet, keep `dados_base["barbearia"]` here and let Task 6's sweep fix it).

- [ ] **Step 3: Create `test_estabelecimentos_admin.py` with the ported CRUD tests**

```python
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
```

- [ ] **Step 4: Create `test_auth.py` with the ported generic auth tests**

```python
import pytest
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from app.limiter import limiter
from app.models.estabelecimento import Estabelecimento
import app.routes.auth as auth_module
from app.security import hash_senha, verificar_senha


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
```

Note: `test_tenant_header_mismatch_retorna_403` from the old file used `dados_base["barbearia"]` and the `X-Barbearia-Id` header — that test is ported in **Task 5** instead, alongside the header rename, so it exercises the new header name from day one.

- [ ] **Step 5: Delete the old test files**

```bash
git rm backend/tests/test_barbearia_funcionamento.py backend/tests/test_auth_barbearias.py
```

- [ ] **Step 6: Run the full suite**

```bash
cd backend && python -m pytest -q 2>&1 | tail -40
```

Expected: PASS, same total test count as before minus any tests deliberately not ported (there should be none — every unique assertion moved).

- [ ] **Step 7: Commit**

```bash
git add -A backend/tests
git commit -m "test: portar cobertura de test_barbearia_funcionamento.py e test_auth_barbearias.py para os equivalentes estabelecimento/estabelecimentos_admin/auth"
```

---

### Task 5: Rename the public API contract (header + URL paths) — backend and frontend together

**Files:**
- Modify: `backend/app/main.py:171`, `backend/app/routes/deps.py:135`, `backend/app/routes/public.py:17,58,84`, `backend/app/schemas/public.py:32`
- Modify: `backend/tests/conftest.py:175` and any test file using `X-Barbearia-Id`
- Modify: `frontend/services/api.ts:279,617,636`

- [ ] **Step 1: Rename the schema class**

In `backend/app/schemas/public.py:32`, rename `PublicBarbeariaLookupResponse` → `PublicEstabelecimentoLookupResponse`, and update `backend/app/routes/public.py` import + usages:

```bash
perl -pi -e 's/\bPublicBarbeariaLookupResponse\b/PublicEstabelecimentoLookupResponse/g' backend/app/schemas/public.py backend/app/routes/public.py
```

- [ ] **Step 2: Rename the URL paths in `backend/app/routes/public.py`**

```bash
perl -pi -e 's{"/barbearia/\{slug\}"}{"/estabelecimento/{slug}"}; s{"/barbearia-id/\{barbearia_id\}"}{"/estabelecimento-id/{estabelecimento_id}"}' backend/app/routes/public.py
```

Then open `backend/app/routes/public.py` and rename the `barbearia_id` path parameter in the function signature for the `/estabelecimento-id/{estabelecimento_id}` route to `estabelecimento_id` (the path param name must match the `{estabelecimento_id}` placeholder exactly), and any internal usage of that parameter name in the function body.

- [ ] **Step 3: Rename the HTTP header, backend side**

```bash
perl -pi -e 's/X-Barbearia-Id/X-Estabelecimento-Id/g' backend/app/main.py backend/app/routes/deps.py
```

In `backend/app/routes/deps.py:135`, also rename the Python parameter name `x_barbearia_id` → `x_estabelecimento_id` and any usage of it later in that function.

- [ ] **Step 4: Rename the header in the frontend**

```bash
perl -pi -e 's/X-Barbearia-Id/X-Estabelecimento-Id/g' frontend/services/api.ts
```

- [ ] **Step 5: Rename the frontend fetch URLs and param key**

```bash
perl -pi -e 's{/public/barbearia/}{/public/estabelecimento/}; s{/public/barbearia-id/}{/public/estabelecimento-id/}' frontend/services/api.ts
```

Also rename the `barbearia_id` key in the params object passed to the "lookup by id" function (`frontend/services/api.ts` around line 636) to `estabelecimento_id`, and update its one caller in `frontend/app/agendar/[barbeariaId]/page.tsx` (`lookupPublicBarbershopById({ barbearia_id: id })` → `{ estabelecimento_id: id }` — the function itself is renamed in Task 10, so only the param key changes here).

- [ ] **Step 6: Rename the header in test fixtures**

```bash
grep -rln "X-Barbearia-Id" backend/tests --include="*.py" | xargs perl -pi -e 's/X-Barbearia-Id/X-Estabelecimento-Id/g'
```

- [ ] **Step 7: Add the ported `test_tenant_header_mismatch_retorna_403` test to `backend/tests/test_auth.py`**

Append to `backend/tests/test_auth.py` (created in Task 4):

```python
def test_tenant_header_mismatch_retorna_403(client, dados_base, make_tenant_headers):
    token_tenant_correto = make_tenant_headers(dados_base["estabelecimento"].id)
    headers_mismatch = {
        **token_tenant_correto,
        "X-Estabelecimento-Id": str(dados_base["estabelecimento"].id + 999),
    }
    resp = client.get("/clientes/", headers=headers_mismatch)
    assert resp.status_code == 403
```

(If `dados_base["barbearia"]` is still the fixture key at this point because Task 6 hasn't run yet, use that key instead — check with `grep -n "def dados_base" -A 15 backend/tests/conftest.py` before writing this.)

- [ ] **Step 8: Verify no remaining references to the old contract names**

```bash
grep -rn "X-Barbearia-Id\|PublicBarbeariaLookupResponse\|/barbearia/{slug}\|/barbearia-id/" backend frontend --include="*.py" --include="*.ts" --include="*.tsx" | grep -v __pycache__ | grep -v node_modules
```

Expected: no output.

- [ ] **Step 9: Run backend and frontend checks**

```bash
cd backend && python -m pytest -q 2>&1 | tail -30
cd ../frontend && npx tsc --noEmit 2>&1 | tail -30
```

Expected: backend PASS. Frontend will still show errors for identifiers renamed in later tasks (`lookupPublicBarbershop`, `BarbershopWorkingHours`, etc.) — that's expected here, they're fixed in Task 10.

- [ ] **Step 10: Commit**

```bash
git add -A backend/app backend/tests frontend/services/api.ts
git commit -m "refactor(api): renomear contrato publico — header X-Barbearia-Id e rotas /public/barbearia* para Estabelecimento"
```

---

### Task 6: Remove ORM legacy aliases and the `models/barbearia.py` shim

**Files:**
- Modify (consumers, `.barbearia_id` → `.estabelecimento_id`, in `app/`): `backend/app/repositories/booking_repository.py`, `backend/app/routes/public.py`, `backend/app/routes/dashboard.py`, `backend/app/routes/servicos.py`, `backend/app/routes/clientes.py`, `backend/app/routes/agendamentos.py`, `backend/app/routes/agenda.py`, `backend/app/services/agendamento_service.py`, `backend/app/services/agenda_service.py`, `backend/app/services/scheduler.py`, `backend/app/services/chatbot_service.py`, `backend/app/schemas/public.py`
- Modify (consumers, `.barbearia_id` used as a **model constructor kwarg**, in `tests/` — these break with `TypeError` the moment the synonym is removed if not caught here): `backend/tests/conftest.py`, `backend/tests/test_tenant_isolation.py`, `backend/tests/test_analise_dashboard.py`, `backend/tests/test_scheduler.py`, `backend/tests/test_agendamento.py`, `backend/tests/test_novos_cenarios.py`, `backend/tests/test_public.py`, `backend/tests/test_notificacoes.py`, `backend/tests/test_public_routes_extra.py`, `backend/tests/test_email_service.py`, `backend/tests/test_dashboard_extra.py`, `backend/tests/test_chatbot.py`
- Modify (consumers, `.barbearia` relationship → `.estabelecimento`): `backend/app/services/agendamento_service.py:485`
- Modify (models, remove synonym/relationship/shim): `backend/app/models/servico.py`, `backend/app/models/cliente.py`, `backend/app/models/agendamento.py`
- Delete: `backend/app/models/barbearia.py`
- Modify (importers of the shim, `from app.models.barbearia import Barbearia` → `from app.models.estabelecimento import Estabelecimento`, plus rename `Barbearia` usages to `Estabelecimento`): `backend/app/repositories/tenant_repository.py`, `backend/app/routes/agenda.py`, `backend/app/routes/auth.py`, `backend/app/routes/barbeiros.py`, `backend/app/routes/chatbot.py`, `backend/app/routes/deps.py`, `backend/app/routes/webhooks.py`, `backend/app/routes/whatsapp.py`, `backend/app/services/agenda_service.py`, `backend/app/services/agendamento_service.py`, `backend/app/services/notificacao_service.py`, `backend/app/services/public_booking_service.py`, `backend/scripts/migrate_senhas.py`
- Modify (test files still importing the shim): `backend/tests/test_agendamento.py`, `backend/tests/test_novos_cenarios.py`, `backend/tests/test_public.py`, `backend/tests/test_rotas_cadastros.py`, `backend/tests/test_scheduler.py`, `backend/tests/test_tenant_isolation.py`, `backend/tests/test_webhook_root.py`, `backend/tests/test_webhooks.py`, `backend/tests/test_whatsapp.py`
- Modify (the `dados_base` fixture's dict key `"barbearia"` → `"estabelecimento"`, plus its consumers): `backend/tests/conftest.py`, `backend/tests/test_agendamento.py`, `backend/tests/test_agenda.py`, `backend/tests/test_estabelecimento_funcionamento.py`, `backend/tests/test_notificacoes.py`, `backend/tests/test_security_audit.py`, `backend/tests/test_chatbot.py` (`test_barbearia_funcionamento.py` and `test_auth_barbearias.py` also used this key but were already deleted in Task 4)

This task must run in this exact order: rename all consumers first (safe no-op while the synonym/relationship/shim still exist), then delete the legacy declarations, then verify. **Do not skip the `tests/` half of Step 1** — `barbearia_id=` is used as a real SQLAlchemy model constructor keyword argument in a dozen test files (e.g. `Profissional(nome="Joao", barbearia_id=barbearia.id)` in `conftest.py`), not just as attribute access. Once the synonym is removed from the models, every one of those constructor calls raises `TypeError: invalid keyword argument` unless already renamed.

- [ ] **Step 1: Rename `barbearia_id` (attribute access AND constructor kwarg) to `estabelecimento_id` everywhere, in both `app/` and `tests/`**

```bash
grep -rl "barbearia_id" backend/app backend/tests backend/scripts --include="*.py" | grep -v __pycache__ | xargs perl -pi -e 's/\bbarbearia_id\b/estabelecimento_id/g'
```

This is a blanket rename of the token `barbearia_id` across the whole backend (app, tests, and scripts) so both attribute access (`Agendamento.barbearia_id == tenant_id`) and constructor/keyword usages (`Servico(..., barbearia_id=x.id)`, `barbearia_id=dados.barbearia_id`) are caught in the same pass.

- [ ] **Step 1b: Rename the `dados_base` fixture's dict key from `"barbearia"` to `"estabelecimento"`**

In `backend/tests/conftest.py`, in the `dados_base` fixture, rename the local variable `barbearia` to `estabelecimento` and the returned dict key `"barbearia"` to `"estabelecimento"`:

```python
@pytest.fixture
def dados_base(db_session):
    estabelecimento = Estabelecimento(nome="Estabelecimento Teste", endereco="Rua Teste, 123")
    db_session.add(estabelecimento)
    db_session.commit()
    db_session.refresh(estabelecimento)

    barbeiro = Profissional(nome="Joao", estabelecimento_id=estabelecimento.id)
    servico = Servico(
        nome="corte social",
        duracao_minutos=40,
        preco=40.0,
        estabelecimento_id=estabelecimento.id,
    )
    db_session.add_all([barbeiro, servico])
    db_session.commit()
    db_session.refresh(barbeiro)
    db_session.refresh(servico)

    return {
        "estabelecimento": estabelecimento,
        "barbeiro": barbeiro,
        # ... (keep every other key in the original return dict unchanged)
    }
```

(Read the full current fixture with `sed -n '120,150p' backend/tests/conftest.py` first — only `barbearia`/`"barbearia"` change, every other key like `"barbeiro"`, `"servico"`, etc. stays as-is.)

Then update every consumer of `dados_base["barbearia"]`:

```bash
for f in backend/tests/test_agendamento.py backend/tests/test_agenda.py backend/tests/test_estabelecimento_funcionamento.py backend/tests/test_notificacoes.py backend/tests/test_security_audit.py backend/tests/test_chatbot.py; do
  perl -pi -e 's/dados_base\["barbearia"\]/dados_base["estabelecimento"]/g' "$f"
done
```

- [ ] **Step 2: Rename the `.barbearia` relationship access in `agendamento_service.py:485`**

```bash
perl -pi -e 's/agendamento\.barbearia\b/agendamento.estabelecimento/; s/db\.query\(Barbearia\)/db.query(Estabelecimento)/' backend/app/services/agendamento_service.py
```

(The `Barbearia` → `Estabelecimento` class reference on that same line is fixed properly in Step 4 below; this early pass just keeps the relationship attribute consistent.)

- [ ] **Step 3: Remove the synonym declarations and relationship alias from the models**

In `backend/app/models/servico.py`, `backend/app/models/cliente.py`: delete the line `barbearia_id = synonym("estabelecimento_id")` (and the `synonym` import if it becomes unused in that file — check with `grep -n synonym backend/app/models/servico.py backend/app/models/cliente.py` after removing).

In `backend/app/models/agendamento.py`: delete the line `barbearia_id = synonym("estabelecimento_id")` and the `barbearia = relationship("Estabelecimento", foreign_keys=[estabelecimento_id], overlaps="estabelecimento")` line, plus its explanatory comment (`# Aliases de relacionamento para código legado que acessa .barbeiro / .barbearia` — keep the `.barbeiro` part of that comment if it still applies to a different alias, otherwise delete the whole comment).

- [ ] **Step 4: Delete the `models/barbearia.py` shim and repoint its 12 app-code importers**

```bash
git rm backend/app/models/barbearia.py
for f in backend/app/repositories/tenant_repository.py backend/app/routes/agenda.py backend/app/routes/auth.py backend/app/routes/barbeiros.py backend/app/routes/chatbot.py backend/app/routes/deps.py backend/app/routes/webhooks.py backend/app/routes/whatsapp.py backend/app/services/agenda_service.py backend/app/services/agendamento_service.py backend/app/services/notificacao_service.py backend/app/services/public_booking_service.py backend/scripts/migrate_senhas.py; do
  perl -pi -e 's/from app\.models\.barbearia import Barbearia/from app.models.estabelecimento import Estabelecimento/' "$f"
  perl -pi -e 's/\bBarbearia\b/Estabelecimento/g' "$f"
done
```

- [ ] **Step 5: Repoint the 9 test files that import the shim**

```bash
for f in backend/tests/test_agendamento.py backend/tests/test_novos_cenarios.py backend/tests/test_public.py backend/tests/test_rotas_cadastros.py backend/tests/test_scheduler.py backend/tests/test_tenant_isolation.py backend/tests/test_webhook_root.py backend/tests/test_webhooks.py backend/tests/test_whatsapp.py; do
  perl -pi -e 's/from app\.models\.barbearia import Barbearia/from app.models.estabelecimento import Estabelecimento/' "$f"
  perl -pi -e 's/\bBarbearia\b/Estabelecimento/g' "$f"
done
```

- [ ] **Step 6: Fix any variable named `barbearia` (lowercase) left dangling by the class rename**

The blanket `\bBarbearia\b` → `Estabelecimento` rename above only touches the PascalCase class name. Any local variable literally named `barbearia` (lowercase) still reads fine syntactically (it's just a variable name pointing to an `Estabelecimento` instance) but is inconsistent — Task 7 sweeps those. Do not rename lowercase `barbearia` in this task; keep this task scoped to the shim removal so `git diff` stays reviewable.

- [ ] **Step 7: Verify the shim is fully gone**

```bash
grep -rn "app\.models\.barbearia\|models/barbearia" backend --include="*.py" | grep -v __pycache__
grep -rn "synonym(\"estabelecimento_id\")\|synonym('estabelecimento_id')" backend/app/models
```

Expected: no output for either.

- [ ] **Step 8: Run the full backend suite**

```bash
cd backend && python -m pytest -q 2>&1 | tail -40
```

Expected: PASS. If any test fails on `AttributeError: 'Servico' object has no attribute 'barbearia_id'` or similar, grep that exact file for a `barbearia_id` occurrence Step 1's file list missed and fix it directly — the synonym removal means every occurrence must have been caught.

- [ ] **Step 9: Commit**

```bash
git add -A backend/app backend/scripts backend/tests
git commit -m "refactor(models): remover shim models/barbearia.py e aliases synonym/relationship barbearia_id/.barbearia"
```

---

### Task 7: Sweep remaining lowercase `barbearia` identifiers

**Files:** whatever remains after Tasks 1–6, across `app/`, `scripts/`, **and `tests/`** — this task starts with a fresh grep rather than a fixed file list, since prior tasks change what's left. Note that most of the remaining volume at this point is in `tests/` (local variable names inside individual test functions that Task 6 didn't touch, e.g. a test-local `barbearia = Estabelecimento(...)` that isn't part of the shared `dados_base` fixture).

- [ ] **Step 1: List what's left**

```bash
cd backend && grep -rn "barbearia" app scripts tests --include="*.py" -i | grep -v __pycache__
```

- [ ] **Step 2: Triage each remaining hit into one of three buckets**

1. **Local variable/parameter names** (e.g. `def foo(barbearia): ...`, `barbearia = db.query(...)`, or a test-local `barbearia = Estabelecimento(...)`) — rename to `estabelecimento` with `perl -pi -e 's/\bbarbearia\b/estabelecimento/g' <file>`, then re-read the function to make sure the rename didn't collide with an existing `estabelecimento` variable already in scope (if it did, pick a non-colliding name and adjust manually — do not blanket-rename in that file).
2. **Data value literal** `"barbearia"` used as `Estabelecimento.tipo_servico` default or compared against (`tipo_servico == "barbearia"`) — **do not touch**, this is the explicitly out-of-scope business-data value.
3. **Comments/docstrings mentioning "barbearia" as prose** — rename to "estabelecimento" for consistency, plain text edit.

- [ ] **Step 3: Re-run the grep to confirm only bucket-2 (data value) hits remain**

```bash
grep -rn "barbearia" app scripts tests --include="*.py" -i | grep -v __pycache__
```

Expected: every remaining line is a `tipo_servico` comparison/default with the literal string `"barbearia"` — nothing else.

- [ ] **Step 4: Run the full suite**

```bash
python -m pytest -q 2>&1 | tail -20
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A backend/app backend/scripts backend/tests
git commit -m "refactor: renomear variaveis/parametros locais 'barbearia' remanescentes para 'estabelecimento'"
```

---

### Task 8: Final backend verification

- [ ] **Step 1: Full repo-wide backend grep, excluding intentional exceptions**

```bash
cd backend && grep -rn "barbearia\|barbershop" app scripts tests --include="*.py" -i | grep -v __pycache__ | grep -v "tipo_servico"
```

Expected: no output. If anything shows up, fix it before continuing — this is the safety net for anything Tasks 1–7 missed.

- [ ] **Step 2: Confirm Alembic history was untouched**

```bash
git status alembic/versions/ 2>/dev/null || git status backend/alembic/versions/
```

Expected: no changes (migration files are never edited by this plan).

- [ ] **Step 3: Full test suite one more time**

```bash
cd backend && python -m pytest -q
```

Expected: PASS, all tests.

---

## Frontend

### Task 9: Reconcile admin service files

**Files:**
- Delete: `frontend/services/barbershops-admin.ts`
- Modify: `frontend/services/estabelecimentos-admin.ts` (remove back-compat aliases)
- Modify: `frontend/app/admin/master/page.tsx` (use canonical names)

- [ ] **Step 1: Confirm `barbershops-admin.ts` really has zero importers**

```bash
grep -rln "barbershops-admin" frontend/app frontend/services frontend/components 2>/dev/null | grep -v node_modules
```

Expected: no output.

- [ ] **Step 2: Delete it**

```bash
git rm frontend/services/barbershops-admin.ts
```

- [ ] **Step 3: Remove the "Backward compat alias" block at the end of `estabelecimentos-admin.ts`**

Open `frontend/services/estabelecimentos-admin.ts` and delete these exports (they sit in a block(s) commented `// Backward compat alias`/`// Backward compat aliases`):

```typescript
export type BarbeariaAdmin = EstabelecimentoAdmin;
export type PlanoBarbearia = PlanoEstabelecimento;
export type StatusManualBarbearia = StatusManualEstabelecimento;
export type StatusAssinaturaBarbearia = StatusAssinaturaEstabelecimento;
```
```typescript
export const listBarbeariasAdmin = listEstabelecimentosAdmin;
```
```typescript
export const createBarbeariaAdmin = createEstabelecimentoAdmin;
```
```typescript
export const updateBarbeariaAdmin = updateEstabelecimentoAdmin;
```
```typescript
export const deleteBarbeariaAdmin = deleteEstabelecimentoAdmin;
```
```typescript
export const getStatusAssinaturaBarbearia = getStatusAssinaturaEstabelecimento;
```

- [ ] **Step 4: Update `admin/master/page.tsx` to import and use the canonical names**

```bash
perl -pi -e '
  s/\bBarbeariaAdmin\b/EstabelecimentoAdmin/g;
  s/\bPlanoBarbearia\b/PlanoEstabelecimento/g;
  s/\bStatusManualBarbearia\b/StatusManualEstabelecimento/g;
  s/\bStatusAssinaturaBarbearia\b/StatusAssinaturaEstabelecimento/g;
  s/\blistBarbeariasAdmin\b/listEstabelecimentosAdmin/g;
  s/\bcreateBarbeariaAdmin\b/createEstabelecimentoAdmin/g;
  s/\bupdateBarbeariaAdmin\b/updateEstabelecimentoAdmin/g;
  s/\bdeleteBarbeariaAdmin\b/deleteEstabelecimentoAdmin/g;
  s/\bgetStatusAssinaturaBarbearia\b/getStatusAssinaturaEstabelecimento/g;
' frontend/app/admin/master/page.tsx
```

- [ ] **Step 5: Verify**

```bash
grep -n "Barbearia\|barbershop" frontend/app/admin/master/page.tsx frontend/services/estabelecimentos-admin.ts -i
```

Expected: no output.

- [ ] **Step 6: Typecheck**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i "admin/master\|estabelecimentos-admin"
```

Expected: no output (no new errors in these two files — other files still have pending renames from Task 10).

- [ ] **Step 7: Commit**

```bash
git add -A frontend/services frontend/app/admin/master/page.tsx
git commit -m "refactor(frontend): remover barbershops-admin.ts morto e aliases de compat em estabelecimentos-admin.ts"
```

---

### Task 10: Rename remaining `Barbershop*` identifiers in `services/api.ts` and consumers

**Files:**
- Modify: `frontend/services/api.ts`
- Modify: `frontend/app/gestao/page.tsx`, `frontend/app/[slug]/page.tsx`, `frontend/app/reagendar/[token]/page.tsx`, `frontend/app/agendar/[barbeariaId]/page.tsx`, `frontend/app/components/BookingTokenActionCard.tsx`, `frontend/services/auth.ts`

- [ ] **Step 1: Rename the type and function identifiers across all affected files in one pass**

```bash
files="frontend/services/api.ts frontend/app/gestao/page.tsx frontend/app/[slug]/page.tsx frontend/app/reagendar/[token]/page.tsx frontend/app/agendar/[barbeariaId]/page.tsx frontend/app/components/BookingTokenActionCard.tsx frontend/services/auth.ts"
for f in $files; do
  perl -pi -e '
    s/\bBarbershopWorkingHours\b/EstabelecimentoWorkingHours/g;
    s/\bdefaultBarbershopWorkingHours\b/defaultEstabelecimentoWorkingHours/g;
    s/\bgetBarbershopWorkingHours\b/getEstabelecimentoWorkingHours/g;
    s/\bupdateBarbershopWorkingHours\b/updateEstabelecimentoWorkingHours/g;
    s/\blookupPublicBarbershopById\b/lookupPublicEstabelecimentoById/g;
    s/\blookupPublicBarbershop\b/lookupPublicEstabelecimento/g;
    s/\bbarbershop_id\b/estabelecimento_id/g;
  ' "$f"
done
```

- [ ] **Step 2: Verify**

```bash
grep -rn "Barbershop\|barbershop" frontend/services/api.ts frontend/app/gestao/page.tsx "frontend/app/[slug]/page.tsx" "frontend/app/reagendar/[token]/page.tsx" "frontend/app/agendar/[barbeariaId]/page.tsx" frontend/app/components/BookingTokenActionCard.tsx frontend/services/auth.ts
```

Expected: no output.

- [ ] **Step 3: Typecheck**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -30
```

Expected: only errors remaining should be about `barbeariaId` in the still-unrenamed route folder (fixed in Task 11).

- [ ] **Step 4: Commit**

```bash
git add -A frontend/services frontend/app
git commit -m "refactor(frontend): renomear BarbershopWorkingHours/lookupPublicBarbershop* para Estabelecimento em services/api.ts e consumidores"
```

---

### Task 11: Rename dynamic route folder `[barbeariaId]` → `[estabelecimentoId]`

**Files:**
- Move: `frontend/app/agendar/[barbeariaId]/page.tsx` → `frontend/app/agendar/[estabelecimentoId]/page.tsx`

- [ ] **Step 1: Move the folder**

```bash
git mv "frontend/app/agendar/[barbeariaId]" "frontend/app/agendar/[estabelecimentoId]"
```

- [ ] **Step 2: Update the param name inside the moved file**

In `frontend/app/agendar/[estabelecimentoId]/page.tsx`:

```typescript
"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { lookupPublicEstabelecimentoById } from "@/services/api";

export default function RedirectToSlugPage() {
  const params = useParams<{ estabelecimentoId: string }>();
  const router = useRouter();

  useEffect(() => {
    const id = Number(params?.estabelecimentoId);
    if (!Number.isFinite(id)) {
      router.replace("/");
      return;
    }
    lookupPublicEstabelecimentoById({ estabelecimento_id: id })
      .then((data) => router.replace(`/${data.slug}`))
      .catch(() => router.replace("/"));
  }, [params, router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-900">
      <p className="text-sm text-zinc-400">Redirecionando...</p>
    </main>
  );
}
```

This is a pure internal rename — the external URL stays `/agendar/{id}` (Next.js dynamic segment folder names don't appear in the URL), so no bookmarked links break.

- [ ] **Step 3: Verify**

```bash
grep -rn "barbeariaId" frontend/app --include="*.tsx" --include="*.ts" | grep -v node_modules
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add -A "frontend/app/agendar"
git commit -m "refactor(frontend): renomear rota dinamica [barbeariaId] para [estabelecimentoId]"
```

---

### Task 12: Final frontend verification

- [ ] **Step 1: Full repo-wide frontend grep**

```bash
grep -rn "barbearia\|barbershop" frontend/app frontend/services frontend/components -i --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v "\.next/"
```

Expected: no output.

- [ ] **Step 2: Typecheck and build**

```bash
cd frontend && npx tsc --noEmit && npm run build 2>&1 | tail -40
```

Expected: both succeed with no errors.

---

## Branding + deploy checklist (Fase 2)

### Task 13: Page title, metadata, and package name

**Files:**
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/package.json`

- [ ] **Step 1: Update the metadata export**

In `frontend/app/layout.tsx`, replace:

```typescript
export const metadata: Metadata = {
  title: "Painel de Gestão",
  description: "Plataforma de gestão de agendamentos para estabelecimentos",
};
```

with:

```typescript
export const metadata: Metadata = {
  title: "Hagendei | Painel de Gestão",
  description: "Hagendei — plataforma de gestão de agendamentos para negócios e profissionais",
  openGraph: {
    title: "Hagendei | Painel de Gestão",
    description: "Hagendei — plataforma de gestão de agendamentos para negócios e profissionais",
  },
};
```

- [ ] **Step 2: Rename the package**

In `frontend/package.json:2`, change `"name": "frontend"` to `"name": "hagendei-frontend"`.

- [ ] **Step 3: Verify the app still builds and the title renders**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Then start the dev server and check the browser tab title reads "Hagendei | Painel de Gestão" on `/gestao`.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/layout.tsx frontend/package.json
git commit -m "feat(branding): titulo/metadata da pagina e nome do pacote para Hagendei"
```

---

### Task 14: Domain placeholder in `.env.example`

**Files:**
- Modify: `frontend/.env.example`

- [ ] **Step 1: Update the placeholder**

In `frontend/.env.example:2`, change:

```
NEXT_PUBLIC_API_URL=https://api.seudominio.com
```

to:

```
NEXT_PUBLIC_API_URL=https://api.hagendei.com
```

- [ ] **Step 2: Commit**

```bash
git add frontend/.env.example
git commit -m "docs(env): atualizar placeholder de dominio no .env.example para hagendei.com"
```

---

### Task 15: Repo-wide safety-net sweep and deploy checklist doc

**Files:**
- Create: `docs/deploy-hagendei-checklist.md`

- [ ] **Step 1: Full repo-wide grep, excluding known-safe locations**

```bash
grep -rn "barbearia\|barbershop" . -i \
  --include="*.py" --include="*.ts" --include="*.tsx" --include="*.md" --include="*.json" --include="*.yml" --include="*.yaml" \
  2>/dev/null \
  | grep -v node_modules | grep -v __pycache__ | grep -v "\.next/" | grep -v "/\.git/" \
  | grep -v "\.claude/worktrees/" | grep -v "alembic/versions/" \
  | grep -v "tipo_servico"
```

Review whatever remains — it's most likely `.pytest_cache/`, generated `SYSTEM_REPORT.md`/`.html` (regenerated by a hook, don't hand-edit), or the original repo directory name `barbearia-chatbot` in file paths themselves (not file contents — leave the local folder name as-is, it's not tracked by git). Fix any genuine remaining code/doc reference found; if everything left is one of those excluded categories, move on.

- [ ] **Step 2: Write the deploy checklist**

```markdown
# Checklist de deploy — domínio hagendei.com

Passos manuais (fora do acesso do assistente) para colocar `hagendei.com` no ar
apontando para o servidor de produção atual.

## 1. DNS (Hostinger, ou onde o domínio estiver gerenciado)

Criar dois registros `A` na zona DNS de `hagendei.com`, apontando para o IP
público do servidor onde o Caddy roda hoje:

| Tipo | Host | Valor | TTL |
|------|------|-------|-----|
| A | `hagendei.com` (ou `@`) | `<IP do servidor>` | 3600 (ou automático) |
| A | `api.hagendei.com` | `<IP do servidor>` | 3600 (ou automático) |

Se o frontend também deve responder em `www.hagendei.com`, adicionar um terceiro
registro `A` (ou `CNAME` para `hagendei.com`) para `www`.

## 2. Variáveis de ambiente no servidor de produção

No `.env` de produção (fora do git, direto no servidor), atualizar:

```
APP_DOMAIN=hagendei.com
API_DOMAIN=api.hagendei.com
```

Reiniciar o container do Caddy:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart caddy
```

O Caddy (`Caddyfile` já usa `{$APP_DOMAIN}`/`{$API_DOMAIN}`, nenhuma mudança de
código necessária) emite o certificado TLS automaticamente via Let's Encrypt
assim que o DNS resolver para o IP correto — não é necessário configurar
certificado manualmente.

## 3. Verificação

- [ ] `dig hagendei.com` e `dig api.hagendei.com` resolvem para o IP do servidor.
- [ ] `curl -I https://hagendei.com` retorna `200` (ou redirect esperado) com
      certificado válido.
- [ ] `curl -I https://api.hagendei.com/docs` (ou outro endpoint público)
      retorna `200` com certificado válido.
- [ ] `frontend/.env` de produção (fora do git) tem `NEXT_PUBLIC_API_URL=https://api.hagendei.com`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/deploy-hagendei-checklist.md
git commit -m "docs(deploy): checklist de configuracao manual de DNS/env para hagendei.com"
```

---

## GitHub repository (Fase 3)

### Task 16: Rename the GitHub repository

**This task performs an irreversible-ish action on a shared/public resource (changes the repo's public URL). Confirm explicitly with the user immediately before running Step 1 — do not run it as part of an unattended batch.**

- [ ] **Step 1: Confirm current repo state**

```bash
git remote -v
gh repo view ViniciusLima115/barbershop-chatbot --json name,url
```

- [ ] **Step 2: Rename via `gh` (after explicit user confirmation)**

```bash
gh repo rename hagendei --repo ViniciusLima115/barbershop-chatbot
```

- [ ] **Step 3: Update the local remote**

```bash
git remote set-url origin https://github.com/ViniciusLima115/hagendei.git
git remote -v
```

- [ ] **Step 4: Verify**

```bash
gh repo view --json name,url
git fetch origin
```

Expected: repo name is `hagendei`, `git fetch` succeeds against the new URL.

(No commit needed — this task doesn't change tracked files, only the remote's identity.)
