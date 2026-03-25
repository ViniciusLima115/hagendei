# Spec — Página de Configurações (Spec 2)

**Data:** 2026-03-25
**Status:** Aprovado pelo usuário
**Projeto:** barbearia-chatbot SaaS

---

## Contexto

O sistema já possui uma página `/gestao` para configurações operacionais (serviços, profissionais, horários). Esta spec cobre uma nova página separada `/configuracoes` com foco em conta, identidade visual e preferências do estabelecimento.

Pré-requisitos concluídos (Fase 1 + Fase 2):
- Senhas com bcrypt, JWT via PyJWT, logout com blacklist
- Models `Estabelecimento`/`Profissional`, endpoint `GET /auth/me`
- `tipo_servico` por tenant

---

## Escopo

### O que está incluído
1. **Perfil do Estabelecimento** — nome, endereço, WhatsApp, slug
2. **Troca de Senha** — senha atual + nova senha com validação bcrypt
3. **Tema por Tenant** — accent color, background color, logo URL; aplicado na página pública e no painel admin
4. **Preferências de Notificação** — ativar/desativar lembretes + antecedência em horas

### O que NÃO está incluído
- Upload de arquivo para logo (campo URL simples)
- Tema para emails/notificações
- Configurações de profissionais/serviços (já estão em /gestao)
- Integração das preferências de notificação com o scheduler (armazenadas mas ainda não consumidas — ver nota abaixo)

---

## Arquitetura

### Abordagem de dados: colunas diretas em `estabelecimentos`

Colunas novas adicionadas via `_ensure_configuracoes_columns()` em `database.py`:

| Coluna | Tipo | Default |
|---|---|---|
| `accent_color` | `VARCHAR(7)` | `'#d4930a'` |
| `bg_color` | `VARCHAR(7)` | `'#ffffff'` |
| `logo_url` | `VARCHAR(500)` | `NULL` |
| `notif_ativo` | `BOOLEAN` | `TRUE` |
| `notif_horas_antes` | `INTEGER` | `2` |

Justificativa: colunas explícitas são mais simples de validar e consultar que um JSONB blob. Compatível com o padrão `_ensure_*` já adotado.

**Importante:** Chamar `_ensure_configuracoes_columns()` dentro de `init_db()` em `database.py`, após as chamadas existentes de `_ensure_*`.

---

## Backend

### Novo router: `backend/app/routes/configuracoes.py`
Prefix: `/configuracoes`
Autenticação: `Depends(get_current_claims)` — apenas tenants (não admin).
Checar explicitamente: `if claims.is_admin: raise HTTPException(403, "Endpoint exclusivo para tenants.")`.

#### Modelo a usar
Todos os endpoints do router de configurações devem consultar `Estabelecimento` (não `Barbearia`):
```python
est = db.query(Estabelecimento).filter(Estabelecimento.id == claims.tenant_id).first()
```
Isso é consistente com o padrão adotado em `GET /auth/me` (Fase 2). `Barbearia` é apenas um alias de compatibilidade e não deve ser usado em código novo.

#### Endpoints

**`PATCH /configuracoes/perfil`**
```
Body: { nome, endereco, whatsapp_number, slug }
Validação:
  - slug único: se slug já existe em outro tenant → 409 Conflict { detail: "Slug já está em uso." }
  - whatsapp_number: formato básico (só dígitos e +)
Response: 200 { detail: "Perfil atualizado." }
```

**`PATCH /configuracoes/senha`**
```
Body: { senha_atual, nova_senha }
Validação:
  - verificar_senha(senha_atual, est.senha) → 400 se incorreta
  - len(nova_senha) >= 8 → 422 se muito curta
  - hash_senha(nova_senha) antes de salvar
Response: 200 { detail: "Senha alterada com sucesso." }
Nota: usar db.query(Estabelecimento) — mesmo padrão de GET /auth/me
```

**`PATCH /configuracoes/tema`**
```
Body: { accent_color, bg_color, logo_url }
Validação:
  - accent_color e bg_color: regex `^#[0-9a-fA-F]{6}$` → 422 se inválido
  - logo_url: se fornecido, deve começar com "https://" → 422 se não começar; NULL é aceito
Response: 200 { detail: "Tema atualizado." }
```

**`PATCH /configuracoes/notificacoes`**
```
Body: { notif_ativo, notif_horas_antes }
Validação: notif_horas_antes in [1, 2, 4, 8, 24] → 422 se fora do range
Response: 200 { detail: "Preferências de notificação atualizadas." }
Nota: as preferências são armazenadas mas ainda não consumidas pelo scheduler (limitação conhecida desta spec).
```

### Extensão de `GET /auth/me`
`MeResponse` passa a incluir os campos do tema e notificações com valores default (Pydantic):
```python
accent_color: str = "#d4930a"
bg_color: str = "#ffffff"
logo_url: str | None = None
notif_ativo: bool = True
notif_horas_antes: int = 2
```
**Nota:** O path de admin em `GET /auth/me` retorna antecipadamente com `MeResponse(nome="Administrador", ...)` sem consultar `Estabelecimento` — os novos campos retornarão seus valores default do Pydantic para admins, o que é correto (admin não tem tema próprio).

### Extensão de `GET /public/estabelecimento/{slug}`
O endpoint público existente deve passar a incluir `accent_color`, `bg_color` e `logo_url` na resposta, para que a página pública `/[slug]` possa aplicar o tema do tenant. Atualizar o schema de resposta do endpoint público correspondente.

### Schemas
Novo arquivo `backend/app/schemas/configuracoes.py`:
- `PerfilUpdate`
- `SenhaUpdate`
- `TemaUpdate`
- `NotificacoesUpdate`

### Testes (TDD — test file: `backend/tests/test_configuracoes.py`)
- `test_atualizar_perfil_sucesso`
- `test_atualizar_perfil_slug_duplicado` (espera 409)
- `test_trocar_senha_correto`
- `test_trocar_senha_atual_errada` (espera 400)
- `test_trocar_senha_muito_curta` (espera 422)
- `test_atualizar_tema_sucesso`
- `test_atualizar_tema_cor_invalida` (espera 422)
- `test_atualizar_tema_logo_url_invalida` (espera 422 — URL sem https://)
- `test_atualizar_notificacoes_sucesso`
- `test_atualizar_notificacoes_horas_invalidas` (espera 422)
- `test_configuracoes_requer_autenticacao` (espera 401 sem token)
- `test_admin_nao_acessa_configuracoes` (espera 403 com token de admin)
- `test_me_retorna_campos_de_tema`

---

## Frontend

### Nova página: `frontend/app/configuracoes/page.tsx`
- Protegida pelo middleware — adicionar `/configuracoes` e `/configuracoes/:path*` à lista `isProtectedPath` E ao array `config.matcher` em `frontend/middleware.ts`
- Não acessível para admin: checar `session.is_admin === true` → redirecionar para `/admin`

### Layout: Sidebar + Conteúdo
```
┌─────────────┬──────────────────────────────┐
│ ⚙ Config.   │                              │
│             │  [seção ativa]               │
│ ● Perfil    │                              │
│   Senha     │  formulário da seção         │
│   Tema      │                              │
│   Notif.    │                              │
└─────────────┴──────────────────────────────┘
```
- Sidebar fixa, estado `activeSection` local (React `useState`)
- Em mobile: sidebar vira menu dropdown/accordion

### Adição ao Header
Novo item "Configurações" no nav do `Header.tsx` (ícone de engrenagem), visível apenas para tenants logados (não admin).

### Sistema de Tema por Tenant

#### Carregamento
1. No login, `GET /auth/me` retorna `accent_color`, `bg_color`, `logo_url`
2. Salvos no `localStorage` junto com a sessão (`barbershop_auth_session`)
3. Hook `useTenantTheme()` aplica ao `document.documentElement`:
   ```ts
   document.documentElement.style.setProperty("--accent", accentColor)
   document.documentElement.style.setProperty("--bg-tenant", bgColor)
   ```
4. Script de early injection (no `<head>`) previne flash ao recarregar — ler `barbershop_auth_session` do localStorage e aplicar CSS vars antes do React hidratar

#### Página pública `/[slug]`
- Busca dados do estabelecimento via `GET /public/estabelecimento/{slug}` (endpoint existente, estendido nesta spec para incluir campos de tema)
- Aplica tema localmente na página apenas (não afeta o resto da SPA)

#### Preview ao vivo
- Na seção Tema, mudança de cor aplica `style.setProperty` imediatamente
- "Salvar" → `PATCH /configuracoes/tema` → atualiza `localStorage`

### Seção Tema
- `<input type="color">` para accent_color e bg_color
- Campo texto para logo_url + `<img>` de preview (com fallback se URL inválida)
- Botão "Salvar tema"

### Seção Notificações
- Toggle (checkbox estilizado) para `notif_ativo`
- `<select>` com opções: 1h, 2h, 4h, 8h, 24h
- Botão "Salvar preferências"

### Seção Senha
- Campos: senha atual · nova senha · confirmar nova senha
- Validação client-side: mínimo 8 chars, confirmação igual
- Feedback de erro inline (não toast)

### Seção Perfil
- Campos: nome, endereço, WhatsApp, slug
- Validação client-side básica antes do PATCH
- Mostrar URL da página pública baseada no slug atual

---

## Fluxo de Dados

```
Login → GET /auth/me → salva tema no localStorage
                     ↓
             useTenantTheme() aplica CSS vars
                     ↓
           /configuracoes/tema → PATCH → atualiza localStorage + reaplicar vars
```

---

## Limitações Conhecidas

- **Notificações não integradas ao scheduler:** As preferências `notif_ativo` e `notif_horas_antes` são armazenadas corretamente mas `notificacao_service.py` e o scheduler ainda não as consomem. A integração está fora do escopo desta spec.

---

## Instruções de Deploy

1. Backend: `git pull` + reiniciar serviço — `init_db()` executa `_ensure_configuracoes_columns()` automaticamente
2. Frontend: `npm run build` + deploy
3. Sem necessidade de script de migração de dados (defaults cobrem todos os registros existentes)
