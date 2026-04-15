# Prompt para VS Code / Cursor — Generalização e Correção de Lógica de Agendamento

Cole este prompt diretamente no chat do Cursor ou Claude Code dentro do VS Code.

---

## CONTEXTO DO PROJETO

Este é um sistema de agendamento multi-tenant construído com:
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL
- **Frontend**: Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS

O sistema nasceu como software para barbearia, mas precisa ser generalizado para **qualquer tipo de estabelecimento que atenda por agendamento** (clínicas, estúdios, salões, oficinas, consultórios, etc.).

---

## PROBLEMAS A CORRIGIR

### PROBLEMA 1 — Lógica de grade de horários com intervalo fixo de 40 minutos

**Onde está o bug:**

`backend/app/services/barbershop_hours_service.py`, função `build_day_slots`:

```python
def build_day_slots(barbearia, target_date, duration_minutes, barbeiro=None):
    ...
    while current + timedelta(minutes=duration_minutes) <= finish:
        slots.append(current)
        current += timedelta(minutes=INTERVALO_MINUTOS)  # ← PROBLEMA: passo fixo em 40 min
```

`backend/app/routes/agenda.py`, linha onde `build_day_slots` é chamado:

```python
for slot in build_day_slots(barbearia, data.date(), INTERVALO_MINUTOS, barbeiro=barbeiro)
# ↑ PROBLEMA: passa INTERVALO_MINUTOS como duration, mas o intervalo de passo também é INTERVALO_MINUTOS
```

**Resultado do bug:** se um agendamento existe às 17:00, mas a grade vai 16:00 → 16:40 → 17:20, o horário 17:00 não aparece na agenda.

**Correção esperada:**

1. A função `build_day_slots` deve receber dois parâmetros distintos:
   - `duration_minutes`: duração do serviço (usado para verificar se o slot cabe antes do fim do expediente)
   - `interval_minutes`: passo entre os slots ofertados na grade (padrão configurável, atualmente 40 min)

2. O modelo `Estabelecimento` (tabela `barbearias`) deve ter um campo `intervalo_minutos: int` com default 30 (mais genérico que 40). Se o campo já não existir, criar a migration Alembic correspondente.

3. O endpoint `GET /agenda/dia` deve ler o `intervalo_minutos` do estabelecimento, **não** de uma variável de ambiente global.

4. O endpoint `GET /agenda/horarios-disponiveis` (em `agenda_service.py`) também deve usar o `intervalo_minutos` do estabelecimento.

5. `INTERVALO_MINUTOS` em `config.py` passa a ser apenas o **fallback padrão**, usado somente quando o estabelecimento não tiver o campo preenchido.

---

### PROBLEMA 2 — Agendamentos fora da grade não aparecem na agenda visual

**Onde está o bug:**

`backend/app/routes/agenda.py`:

```python
horarios = sorted({hora for itens in horarios_por_barbeiro.values() for hora in itens})
# ↑ Apenas os slots da grade. Agendamentos em horários "fora da grade" ficam invisíveis.
```

**Correção esperada:**

Após buscar os `agendamentos` do dia, mesclar os horários reais dos agendamentos no set de horários da resposta:

```python
booking_times = {ag.data_hora_inicio.strftime("%H:%M") for ag in agendamentos}
horarios = sorted(
    {hora for itens in horarios_por_barbeiro.values() for hora in itens} | booking_times
)
```

Isso garante que **todo agendamento existente sempre apareça na agenda**, mesmo que seu horário não esteja alinhado com a grade padrão.

---

### PROBLEMA 3 — Frontend com textos e variáveis hardcoded de "barbearia/barbeiro"

O sistema já tem `frontend/lib/vocab.ts` com um mapa de vocabulário por tipo de estabelecimento, mas o frontend ainda usa termos hardcoded em vários lugares. Corrigir todos os pontos abaixo:

#### 3a. `frontend/app/agenda/page.tsx`

- Variável `selectedBarbeiroId` → renomear para `selectedProfissionalId`
- Texto `"Todos os barbeiros"` → usar `"Todos os profissionais"` (ou `"Todos os ${vocab.profissionalPlural}"` se o vocab estiver disponível no contexto admin)
- Texto `"Barbeiro"` no `<label>` do filtro → `"Profissional"`
- Texto na descrição: `"Veja a disponibilidade por barbeiro..."` → `"Veja a disponibilidade por profissional..."`
- Texto na legenda: `"Fora do expediente do barbeiro"` → `"Fora do expediente do profissional"`
- Referências `barbeiro` nos comentários e IDs HTML → `profissional`

#### 3b. `frontend/app/components/AgendaGrid.tsx`

- Tipo `SelectedAgendamento`: campo `barbeiroId` → `profissionalId`, campo `barbeiroNome` → `profissionalNome`
- Texto `"slots validos no dia"` pode permanecer genérico (ok)
- O componente recebe `data: AgendaDiaResponse`; o campo `barbeiros` na resposta da API pode ser mantido internamente, mas os labels visíveis devem usar vocabulário genérico

#### 3c. `frontend/app/components/AgendaCell.tsx`

- Qualquer prop ou texto que mencione "barbeiro" explicitamente deve ser renomeado para "profissional"

#### 3d. `frontend/lib/vocab.ts`

- O `defaultVocab` atualmente aponta para `vocabMap["barbearia"]`. Mudar o default para um vocabulário neutro:

```typescript
const defaultVocab: VocabEntry = {
  profissional: "Profissional",
  estabelecimento: "Estabelecimento",
  profissionalPlural: "Profissionais",
};
```

- Manter os mapeamentos específicos (barbearia, salao_beleza, estetica_automotiva) para quando o `tipo_servico` for conhecido.

#### 3e. `frontend/app/agendar/[barbeariaId]/page.tsx`

- O parâmetro de rota `[barbeariaId]` é interno e pode permanecer por compatibilidade de URL, mas:
  - Qualquer texto visível ao usuário que diga "barbearia" deve usar o vocab do estabelecimento
  - Labels como "Escolha o barbeiro" → `"Escolha o ${vocab.profissional}"`
  - Titles e headings → usar vocab dinâmico

#### 3f. `frontend/services/api.ts`

- Tipos como `AgendaBarbeiro` podem ser mantidos internamente por compatibilidade, mas adicionar alias de tipo:
  ```typescript
  export type AgendaProfissional = AgendaBarbeiro; // alias genérico
  ```
- A URL base `NEXT_PUBLIC_API_URL` já vem de env — não alterar, mas remover qualquer valor default hardcoded que mencione "barber" ou "barbearia" do código fonte (mover para `.env.example`)

---

### PROBLEMA 4 — Gestão: campo `intervalo_minutos` no painel admin

No painel de gestão (`frontend/app/gestao/`), na seção de configurações do estabelecimento:

- Adicionar campo de formulário `"Intervalo entre horários (minutos)"` que salve `intervalo_minutos` no estabelecimento
- Valor mínimo: 5 minutos, máximo: 120 minutos, step: 5
- Exibir dica: `"Define o espaçamento entre os slots disponíveis na agenda. Ex: 30 min gera horários como 09:00, 09:30, 10:00..."`
- Este campo deve ser salvo via `PATCH /estabelecimento` (ou o endpoint equivalente de update do estabelecimento)

---

### PROBLEMA 5 — Referências de domínio hardcoded

Buscar e substituir em **todo o frontend e backend**:

| Valor atual | Substituir por |
|---|---|
| `virtualbarber.shop` | Variável de ambiente `BOOKING_PUBLIC_BASE_URL` (já existe no `.env`) |
| `agendamentos@virtualbarber.shop` | Variável de ambiente `EMAIL_FROM` |
| `Virtual Barber` (como nome de remetente de email) | Variável de ambiente `EMAIL_FROM_NAME` |
| `barbearia` como valor default de `tipo_servico` na migration/model | Manter por compatibilidade, mas documentar que é legacy |

Adicionar essas variáveis ao `backend/.env.example` (criar se não existir) e ao `frontend/.env.example`.

---

## REGRAS GERAIS PARA TODAS AS ALTERAÇÕES

1. **Não quebrar compatibilidade de API**: os campos internos como `barbeiros`, `barbearia_id`, `barbeiro_id` nos modelos de banco de dados e respostas JSON podem permanecer (são chaves de banco), mas os **textos visíveis ao usuário** no frontend devem ser genéricos.

2. **Migrations Alembic**: qualquer alteração no modelo de banco de dados deve ter uma migration Alembic correspondente em `backend/alembic/versions/`. Usar `alembic revision --autogenerate -m "descricao"` e revisar antes de aplicar.

3. **TypeScript**: todas as alterações no frontend devem manter tipagem forte. Não usar `any`.

4. **Testes**: se existirem testes em `backend/tests/` que dependam de `INTERVALO_MINUTOS=40`, atualizá-los para refletir a nova lógica parametrizada.

5. **Sem regressão na página pública de agendamento** (`/agendar/[barbeariaId]`): a lógica de mostrar horários disponíveis ao cliente final deve continuar funcionando corretamente após as alterações na `build_day_slots`.

---

## ORDEM DE EXECUÇÃO RECOMENDADA

1. Backend: adicionar campo `intervalo_minutos` ao modelo `Barbearia`/`Estabelecimento` + migration Alembic
2. Backend: refatorar `build_day_slots` para aceitar `interval_minutes` separado de `duration_minutes`
3. Backend: atualizar `agenda.py` para ler `intervalo_minutos` do estabelecimento
4. Backend: corrigir merge de `booking_times` no endpoint `/agenda/dia`
5. Backend: atualizar `agenda_service.py` (horários disponíveis) para usar intervalo do estabelecimento
6. Frontend: atualizar `vocab.ts` com default neutro
7. Frontend: corrigir todos os textos hardcoded de "barbeiro/barbearia" nas páginas e componentes
8. Frontend: adicionar campo `intervalo_minutos` no painel de gestão
9. Global: substituir referências de domínio hardcoded por variáveis de ambiente
10. Testes: rodar `pytest backend/tests/` e corrigir eventuais falhas

---

## VERIFICAÇÃO FINAL

Após todas as alterações, confirmar que:

- [ ] Um agendamento criado para 17:00 aparece na agenda mesmo que a grade do dia vá 16:00 → 16:30 → 17:30
- [ ] Alterar `intervalo_minutos` de 40 para 30 no painel de gestão faz a grade mudar corretamente
- [ ] A página pública `/agendar/[id]` continua mostrando horários disponíveis corretamente
- [ ] Nenhum texto visível ao usuário diz "barbeiro" ou "barbearia" quando o tipo do estabelecimento for neutro/desconhecido
- [ ] O email de notificação usa o nome e endereço configurados nas variáveis de ambiente
- [ ] `pytest` passa sem erros
- [ ] `npm run build` no frontend passa sem erros de TypeScript
