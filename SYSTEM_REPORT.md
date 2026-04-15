# Relatório do Sistema — VirtualBarber

**Data:** 2026-03-29
**Domínio:** [virtualbarber.shop](https://virtualbarber.shop) / [app.virtualbarber.shop](https://app.virtualbarber.shop)

---

## Visão Geral

SaaS multi-tenant para gestão de barbearias e salões. O sistema cobre o ciclo completo: o cliente agenda sem precisar criar conta, o dono da barbearia gerencia tudo em um painel, e o sistema automatiza lembretes por e-mail. Existe integração com WhatsApp via MegaAPI.

---

## Arquitetura

```
┌─────────────────────────────────────────┐
│  Frontend — Next.js 14 (App Router)     │
│  app.virtualbarber.shop                 │
└────────────────┬────────────────────────┘
                 │ HTTPS + JWT
┌────────────────▼────────────────────────┐
│  Backend — FastAPI (Uvicorn/Gunicorn)   │
│  api.virtualbarber.shop                 │
└────────────────┬────────────────────────┘
                 │ SQLAlchemy ORM
┌────────────────▼────────────────────────┐
│  Database — PostgreSQL (Neon)           │
└─────────────────────────────────────────┘
```

**Multi-tenancy:** cada estabelecimento é isolado por `tenant_id` — todas as queries filtram por `estabelecimento_id`. O token JWT carrega o `tenant_id` e o plano do dono.

---

## Stack Técnica

| Camada | Tecnologia |
|--------|-----------|
| Frontend | Next.js 14, React 19, TypeScript 5, Tailwind CSS 4 |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2, Python 3.11+ |
| Banco | PostgreSQL (Neon serverless) |
| Auth | JWT HS256, bcrypt, token blacklist |
| Jobs | APScheduler (lembretes automáticos) |
| Charts | Recharts |
| Ícones | Lucide React |
| Rate Limit | slowapi |
| WhatsApp | MegaAPI (webhooks) |

---

## Planos e Limites

| | Grátis | Básico | Premium |
|---|---|---|---|
| Agendamentos/mês | 30 | Ilimitado | Ilimitado |
| Profissionais | 1 | 2 | 3 |
| Dashboard básico | ✗ | ✓ | ✓ |
| Dashboard premium | ✗ | ✗ | ✓ |

---

## Entidades do Banco (11 modelos)

| Modelo | Descrição |
|--------|-----------|
| `Estabelecimento` | Barbearia/salão — contém slug, plano, cores, configurações de notificação |
| `Profissional` | Barbeiro — vinculado ao estabelecimento, com horários e tempos por serviço |
| `Servico` | Serviço oferecido — nome, preço, duração em minutos |
| `Cliente` | Cliente — telefone, nome, vinculado ao estabelecimento |
| `Agendamento` | Agendamento — status, token de confirmação, datas/horas, lembretes enviados |
| `ReminderJob` | Fila de lembretes agendados (24h / 2h antes) |
| `TokenBlacklist` | Tokens JWT invalidados (logout) |
| `WebhookEvent` | Log de webhooks recebidos do MegaAPI |
| `Barbearia` | Alias legado de `Estabelecimento` |
| `Barbeiro` | Alias legado de `Profissional` |

**Status de agendamento:** `pendente` → `confirmado` / `cancelado` / `reagendamento_solicitado`

**No-show:** agendamentos com `status="pendente"` e `data_hora_inicio < agora`.

---

## Endpoints da API

### Autenticação — `/auth`

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/auth/login` | Login (rate-limited); retorna JWT + dados do tenant |
| `GET` | `/auth/me` | Perfil do usuário autenticado |
| `POST` | `/auth/logout` | Invalida o token (blacklist) |
| `POST` | `/auth/admin-check` | Valida credenciais de super-admin |

### Agendamentos — `/agendamentos`

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/agendamentos` | Criar agendamento (painel interno) |
| `GET` | `/agendamentos` | Listar agendamentos do tenant |
| `GET` | `/agendamentos/{token}/dados` | Buscar agendamento pelo token |
| `PATCH` | `/agendamentos/{id}/status` | Atualizar status |
| `POST` | `/agendamentos/{token}/confirmar` | Confirmar via token (e-mail) |
| `POST` | `/agendamentos/{token}/reagendar` | Solicitar reagendamento via token |

### Agenda — `/agenda`

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/agenda/horarios-disponiveis` | Horários disponíveis (barbeiro + serviço + data) |
| `GET` | `/agenda/dia` | Agenda completa do dia |

### Público — `/public` *(sem autenticação)*

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/public/barbearia/{slug}` | Buscar estabelecimento pelo slug |
| `GET` | `/public/barbearia-id/{id}` | Buscar pelo ID |
| `GET` | `/public/servicos` | Listar serviços públicos |
| `GET` | `/public/barbeiros` | Listar barbeiros públicos |
| `GET` | `/public/horarios-disponiveis` | Horários disponíveis (fluxo público) |
| `POST` | `/public/agendamentos` | Criar agendamento público (sem login) |
| `GET` | `/public/{id}/cliente` | Buscar cliente por telefone |

### Clientes / Serviços / Profissionais

CRUD completo (`GET`, `POST`, `PUT`, `DELETE`) com isolamento por tenant.

### Dashboard — `/dashboard` *(premium gate)*

| Método | Rota | Plano | Descrição |
|--------|------|-------|-----------|
| `GET` | `/{id}/resumo-basico` | Básico+ | Agendamentos hoje, mês, faturamento estimado, clientes únicos |
| `GET` | `/{id}/financeiro` | Premium | Faturamento, ticket médio, histórico 12 meses |
| `GET` | `/{id}/servicos-mais-vendidos` | Premium | Top 5 serviços (últimos 30 dias) |
| `GET` | `/{id}/clientes` | Premium | Clientes únicos, novos, recorrentes, top 5 |
| `GET` | `/{id}/analise` | Premium | Resumo do mês, movimento semanal, horários cheios, serviços, retenção |

### Configurações / WhatsApp / Webhooks / Internal

- `PATCH /configuracoes/{perfil,senha,tema,notificacoes}` — atualização de configurações
- `GET|POST /whatsapp/webhook` — receber mensagens do MegaAPI
- `POST /webhooks/megaapi` — processamento de eventos WhatsApp
- `POST /internal/reminders/process` — disparar lembretes (token interno)

---

## Features do Sistema

### Para o Cliente (sem login)

- **Página de agendamento pública** acessível por `/[slug]` ou `/agendar/[id]`
- Escolha de barbeiro, serviço, data e horário disponível
- Formulário com nome, telefone e e-mail opcional
- **Confirmação por e-mail** — link com token único
- **Cancelamento por e-mail** — link com token único
- **Reagendamento por e-mail** — escolha nova data/hora sem precisar de conta
- **Integração WhatsApp** — recebe link de agendamento via WhatsApp

### Para o Dono do Estabelecimento

#### Agenda
- Visualização da agenda do dia em grade de horários
- Criação manual de agendamentos
- Alteração de status (confirmar, cancelar)
- Listagem filtrada por data/barbeiro

#### Gestão
- **Agendamentos** — listagem completa com filtros, criação e edição de status
- **Clientes** — cadastro e listagem
- **Serviços** — CRUD com preço e duração
- **Profissionais** — CRUD com horários individuais e tempos por serviço (respeitando limites do plano)
- **Horários de funcionamento** — configuração semanal (dias ativos, abertura/fechamento)

#### Dashboard

**Plano Básico:**
- Agendamentos confirmados hoje
- Total do mês (confirmados + cancelados)
- Faturamento estimado do mês
- Clientes únicos no mês
- CTA para upgrade ao Premium

**Plano Premium — Aba "Visão Geral":**
- Faturamento do mês vs. mês anterior (variação %)
- Ticket médio por agendamento
- Total de agendamentos confirmados
- Clientes únicos (últimos 30 dias)
- Gráfico de linha — faturamento dos últimos 12 meses
- Painel de clientes: únicos, novos, recorrentes, taxa de cancelamento, top 5 clientes
- Sidebar com top 5 serviços mais vendidos (últimos 30 dias)

**Plano Premium — Aba "Análise" (mês atual):**
- Agendamentos, faturamento, ticket médio, taxa de ocupação
- Gráfico de barras — movimento por dia da semana
- Ranking dos 5 horários mais cheios
- Ranking dos 5 serviços mais vendidos
- Bloco de retenção: clientes novos, recorrentes, cancelamentos, no-show

#### Configurações
- Atualização de perfil (nome, slug, endereço, telefone)
- Troca de senha
- Personalização de tema (7 presets de cor de destaque + modo claro/escuro)
- Configuração de lembretes automáticos (ativar/desativar, horas de antecedência)

#### Lembretes Automáticos
- E-mail 24h antes do agendamento
- E-mail 2h antes do agendamento
- Sistema de fila com controle de duplicatas (APScheduler, roda a cada 1 min)

### Para o Super-Admin

- Painel `/admin/master` — gerenciar todos os estabelecimentos
- Criar, editar, excluir estabelecimentos
- Definir plano (Grátis/Básico/Premium)
- Controlar período de trial e data de vencimento
- Documentação da API (`/docs`) protegida por HTTP Basic Auth

---

## Segurança

- **JWT** HS256, expiração de 8h
- **Blacklist de tokens** — logout invalida o token imediatamente
- **bcrypt** para senhas
- **Rate limiting** no endpoint de login
- **Multi-tenant** — todas as queries filtram por `tenant_id`; 403 se tenant no token ≠ tenant na URL
- **Premium gate** — dependency `verificar_plano_premium` em todos os endpoints de dashboard avançado
- **Tokens de e-mail** — UUIDs únicos para confirmação/cancelamento/reagendamento

---

## Estrutura de Pastas

```
barbearia-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py               # Entry point, middlewares, routers
│   │   ├── config.py             # Variáveis de ambiente
│   │   ├── database.py           # SQLAlchemy engine + Base
│   │   ├── security.py           # JWT + bcrypt
│   │   ├── limiter.py            # slowapi config
│   │   ├── models/               # 11 ORM models
│   │   ├── routes/               # 15 route modules
│   │   ├── schemas/              # Pydantic schemas (request/response)
│   │   ├── services/             # Business logic (12 módulos)
│   │   └── repositories/         # Data access layer
│   └── tests/                    # 162 testes (pytest)
└── frontend/
    ├── app/
    │   ├── [slug]/               # Página pública de agendamento
    │   ├── agendar/[id]/         # Agendamento por ID
    │   ├── agenda/               # Agenda do dia
    │   ├── gestao/               # Painel de gestão
    │   ├── dashboard/            # Analytics
    │   ├── configuracoes/        # Configurações
    │   ├── confirmar/[token]/    # Confirmar agendamento
    │   ├── cancelar/[token]/     # Cancelar agendamento
    │   ├── reagendar/[token]/    # Reagendar
    │   ├── login/                # Autenticação
    │   ├── upgrade/              # Página de planos
    │   └── admin/                # Super-admin
    ├── services/
    │   ├── api.ts                # Cliente HTTP + 40+ funções + tipos TS
    │   └── auth.ts               # Sessão JWT no localStorage
    └── components/               # Componentes reutilizáveis
```

---

## Cobertura de Testes

- **162 testes** no backend (pytest + SQLite in-memory)
- Cobertura: auth, agendamentos, agenda, barbearias, barbeiros, serviços, funcionamento, dashboard (todos os endpoints), webhooks, WhatsApp, public booking, configurações, rate limiting, segurança, isolamento de tenant
