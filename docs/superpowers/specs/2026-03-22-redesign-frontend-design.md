# Redesign Frontend — Barbearia Chatbot

**Data:** 2026-03-22
**Status:** Aprovado pelo usuário

---

## Contexto

O frontend atual usa fontes genéricas (system fonts), tem um shadow azul incorreto nos botões primários (bug), e apesar de ter uma paleta quente decente para barbearias, não transmite profissionalidade suficiente para um produto SaaS vendido a barbearias. O objetivo é elevar o visual ao nível de um produto premium sem quebrar funcionalidades existentes.

---

## Decisões de Design (aprovadas)

| Decisão | Escolha |
|---|---|
| Estilo geral | Editorial Limpo — preto/branco/cinza |
| Navegação | Top Nav (evolução do atual) |
| Cor de destaque | Âmbar/Dourado `#d4930a` |
| Login | Split Screen — esquerda escura com textura diagonal, direita clara |
| Fontes | **Libre Baskerville** (headings) + **Jost** (body) |

---

## Abordagem de Implementação

**Design System First** — reescrever `globals.css` com novos tokens, depois aplicar página por página. Garante coerência total. Cada página é consequência natural dos tokens.

---

## Seção 1 — Design Tokens (globals.css)

### Paleta de Cores

```css
/* Escala de cinzas */
--ink:          #1a1a1a   /* texto principal, headings */
--ink-muted:    #4a4a4a   /* texto secundário */
--ink-subtle:   #9a9a9a   /* placeholders, hints */
--canvas:       #f9f9f7   /* fundo da página */
--surface:      #ffffff   /* cards, painéis */
--surface-alt:  #f0f0ee   /* fundo alternativo, nav pill */
--line:         #e0e0dc   /* bordas, divisores */

/* Acento âmbar */
--accent:       #d4930a   /* botões primários, eyebrows, destaques */
--accent-dark:  #a36f06   /* hover, pressed */
--accent-soft:  #fef3dc   /* badges, highlight backgrounds */
--accent-text:  #a36f06   /* texto sobre --accent-soft */

/* Semânticas (mantidas) */
--success:      #166534
--success-soft: #f0fdf4
--warning:      #854d0e
--warning-soft: #fefce8
--danger:       #991b1b
--danger-soft:  #fef2f2
```

### Tipografia

```css
/* Fontes via next/font/google */
Libre Baskerville — variable: --font-display
  weights: 400, 700 | styles: normal, italic
  uso: h1, h2, h3, h4, números grandes, títulos de cards

Jost — variable: --font-body
  weights: 300, 400, 500, 600, 700
  uso: body, labels, botões, navegação, inputs

/* Eyebrow labels */
font-family: Jost
font-size: 9–11px
font-weight: 700
letter-spacing: 0.14–0.18em
text-transform: uppercase
color: var(--accent) ou var(--ink-subtle)
```

### Sombras

```css
--shadow-sm:  0 1px 4px rgba(0,0,0,0.06)
--shadow-md:  0 4px 16px rgba(0,0,0,0.08)
--shadow-lg:  0 8px 32px rgba(0,0,0,0.10)
```

### Componentes Base

**Botões:**
- Primary: `background #1a1a1a, color white, border-radius 8px`
- Accent: `background #d4930a, color white, border-radius 8px`
- Secondary: `background white, border 1px solid --line, color --ink-muted`
- Outline accent: `background transparent, border 1.5px solid --accent, color --accent`

**Inputs:**
- Default: `background white, border 1px solid --line, border-radius 8px`
- Focus: `border-color --accent, box-shadow 0 0 0 3px rgba(212,147,10,0.12)`

**Badges:**
- Confirmado: `background --success-soft, color --success, border 1px solid #bbf7d0`
- Pendente: `background --warning-soft, color --warning, border 1px solid #fde68a`
- Cancelado: `background --danger-soft, color --danger, border 1px solid #fecaca`
- Livre: `background --surface-alt, color --ink-muted, border 1px solid --line`

---

## Seção 2 — Header

Sticky top nav com:
- **Esquerda:** ícone de tesoura (SVG) em box `#1a1a1a` com acento `#d4930a`, eyebrow "Sistema interno", nome da barbearia em Libre Baskerville
- **Centro:** nav pill (`background --surface-alt, border-radius 10px`) com links; ativo tem `background white, box-shadow` sutil
- **Direita:** botão de tema (ícone) + botão "Sair" com borda

Mobile: nav pill vira grid 2×2, header empilha verticalmente.

---

## Seção 3 — Login (Split Screen)

**Layout:** `grid-template-columns: 1fr 1fr`, altura 100vh mínima.

**Painel Esquerdo (escuro):**
- `background: #1a1a1a`
- Textura diagonal sutil: `repeating-linear-gradient(45deg, rgba(255,255,255,0.02) 0px, rgba(255,255,255,0.02) 1px, transparent 1px, transparent 12px)`
- Conteúdo: logo + eyebrow → título grande em Libre Baskerville → divisor âmbar (28×2px) → social proof (avatares + texto)
- **Sem** radial-gradient — removido por feedback do usuário

**Painel Direito (claro):**
- `background: #f9f9f7`
- Eyebrow âmbar → título "Bem-vindo de volta." em Libre Baskerville → subtítulo itálico → campos → botão submit preto full-width
- Footer: link de suporte âmbar

**Mobile:** empilha verticalmente — painel esquerdo comprime para ~180px, formulário ocupa o restante.

---

## Seção 4 — Dashboard (/)

**Hero card** (`background white, border 1px solid --line, border-radius 14px`):
- Grid 2 colunas: cópia à esquerda (eyebrow + título grande + subtítulo + ações), aside à direita com 2 highlight cards (hoje + taxa de ocupação)

**Stats row:** 4 cards iguais — ícone âmbar-soft + label + valor em Libre Baskerville + helper text

**Content grid** (2 colunas):
- Atalhos rápidos — cards clicáveis com ícone âmbar-soft
- Resumo operacional — lista de status com badges

---

## Seção 5 — Agenda (/agenda)

**Topbar card:** eyebrow âmbar + título com data em Libre Baskerville + seletor de data + botão novo agendamento

**Stats row:** 4 cards — Total / Confirmados (verde) / Disponíveis / Ocupação (âmbar)

**Layout principal** (grid 2 colunas, ~3:1):
- **Grade de agenda:** tabela com colunas por barbeiro × linhas por horário. Cells coloridas por status (verde/amarelo/cinza para livre). Cada cell card tem nome do cliente, serviço e badge de status.
- **Painel lateral:** cards para barbeiros (nome + contagem), legenda, e destaque do próximo horário livre em `background --accent-soft`

---

## Seção 6 — Gestão (/gestao)

Manter estrutura de abas existente. Melhorias visuais:
- Tab bar refinada com tokens do novo design system
- Tabelas com `border-collapse`, `thead` em `--surface-alt`, hover em rows
- Formulários com espaçamento mais generoso e labels em Jost
- Modais com `border-radius 14px`, sombra `--shadow-lg`

---

## Arquivos a Modificar

| Arquivo | Mudança |
|---|---|
| `frontend/app/layout.tsx` | Substituir `Cormorant_Garamond + Outfit` por `Libre_Baskerville + Jost` |
| `frontend/app/globals.css` | Reescrever tokens completos, heading styles, componentes base |
| `frontend/app/components/Header.module.css` | Aplicar novo design |
| `frontend/app/login/page.module.css` | Split screen layout completo |
| `frontend/app/page.module.css` | Hero + stats + content grid |
| `frontend/app/agenda/page.module.css` | Topbar + grade + side panel |
| `frontend/app/gestao/page.module.css` | Refinamentos de tabs e formulários |
| `frontend/app/components/Header.tsx` | Nenhuma mudança lógica, apenas CSS |

---

## O que NÃO muda

- Lógica de autenticação
- Rotas e estrutura de páginas
- Componentes funcionais (Modal, Alert, Badge, etc.) — apenas CSS
- Backend
- Dark mode (mantido, tokens adaptados)
- Páginas públicas (`/agendar`, `/confirmar`, `/cancelar`, `/reagendar`)
