# Redesign Visual — Páginas Públicas (Plano 2 de 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar o mesmo sistema de design do painel admin (azul-petróleo `#1e3a5f` + âmbar `#d99b3f`) às telas voltadas ao cliente final: a página pública de agendamento (`/[slug]`) e as páginas de ação por token (confirmar/cancelar/reagendar), que hoje usam duas paletas hardcoded completamente diferentes (verde/dourado numa, marrom/terracota na outra) e não participam do sistema de variáveis CSS do resto do app.

**Architecture:** Diferente do Plano 1 (painel admin), aqui não há atalho via variável CSS — essas 3 telas usam cor literal (CSS Modules com hex fixo, ou `style={{}}` inline em React) porque são renderizadas fora do layout autenticado e não devem reagir a tema claro/escuro nem a customização por tenant. O trabalho é uma tradução cor-por-cor, seguindo exatamente o mesmo padrão já usado com sucesso no Plano 1 (Task 8, tela de login): trocas de valor literal, escopadas por seletor/contexto, nunca um find-and-replace cego. Também aproveitamos para unificar as cores de sucesso/erro/aviso destas páginas com os tokens exatos já definidos em `frontend/app/globals.css` (`--success`/`--danger`/`--warning` e seus tons suaves), fechando uma inconsistência que já existia antes deste redesign (essas 3 arquivos usavam 2 paletas de verde/vermelho diferentes entre si, nenhuma igual à do painel admin).

**Tech Stack:** Next.js 16 (App Router), TypeScript, CSS Modules, inline React styles.

**Fora de escopo (não mexer):** `frontend/app/agendar/[estabelecimentoId]/page.tsx` é só um redirect para `/[slug]` — não tem estilo próprio, nada a fazer lá. As telas do painel admin (Plano 1) já estão prontas e não são tocadas aqui.

---

## Mapa de cores (referência única — usar em todas as tasks)

| Papel semântico | Valor antigo (varia por arquivo) | Valor novo |
|---|---|---|
| Fundo de página (creme/verde-claro) | `#f5efe7`, `#f2f5f1` | `#f6f8fb` |
| Painel/barra escura (petróleo) | `#1a120b`, `#18201b` (quando usado como fundo escuro) | `#14283f` (sólido) ou gradiente `#1e3a5f → #122840` (quando já era gradiente) |
| Texto "ink" comum (não é o painel escuro) | `#1a120b`, `#18201b`, `#344139` (quando é só texto em fundo claro) | `#1a1a1a` |
| Texto/ícone secundário mais claro | `#4d6958`, `#68736b`, `#748078`, `#526158`, `#718078`, `#778179`, `#7b867f`, `#6b7280`* | `#4a4a4a` (`--ink-muted`) |
| Texto sutil/placeholder | `#9aa49d`, `#9ca3af`, `#a18070` | `#9a9a9a` (`--ink-subtle`) |
| Ícone/selo/label em destaque (âmbar) | `#c36b2d` (quando é label/eyebrow/ícone, não botão), `#f6bc2f`, `#e9b842`, `#f3c456`, `#f2c89a` | `#d99b3f` |
| Botão primário / caixa de ícone de marca / slot selecionado | `#c36b2d` (quando é botão ou caixa da logo), `#1f5e3b` (slot selecionado) | `#1e3a5f` |
| Borda/linha neutra | `#dce3dd`, `#e5d5c5`, `#ccd6ce`, `#cad4cc`, `#e0e0dc`, `#e1e5e2`, `#d5ddd6`, `#cfd7d1` | `#e5e9ee` (`--line`) |
| Superfície alternativa (painel dentro de card) | `#faf7f4`, `#f7f9f7`, `#edf1ed`, `#f3f5f3` | `#f0f2f5` (`--surface-alt`) |
| Foco de input (borda) | `#28794d` | `#1e3a5f` (`--accent`) |
| Foco de input (anel) | `rgba(40,121,77,0.13)` | `rgba(30,58,95,0.16)` (`--accent-ring`) |
| Sucesso (texto) | `#15803d`, `#1d6b41`, `#14532d`, `#166534`(já ok) | `#166534` (`--success`) |
| Sucesso (fundo suave) | `#f0fdf4`(já ok), `#f4fbf6` | `#f0fdf4` (`--success-soft`) |
| Sucesso (borda suave) | `#bbf7d0`(já ok), `#b7d7c2` | `#bbf7d0` (`--success-line`) |
| Aviso/pendente (texto) | `#b45309` | `#854d0e` (`--warning`) |
| Perigo/erro (texto) | `#b91c1c`, `#9f1239`(já quase) | `#991b1b` (`--danger`) |
| Perigo/erro (fundo suave) | `#fff1f2` | `#fef2f2` (`--danger-soft`) |
| Perigo/erro (borda suave) | `#fecdd3` | `#fecaca` (`--danger-line`) |
| Texto claro sobre fundo escuro (subtítulo) | `#e8d5c0` | `rgba(255,255,255,0.75)` |
| Texto de marca sobre fundo escuro | `#f5efe7` (quando é o nome da marca na barra escura) | `#ffffff` |

`*` `#6b7280` aparece em muitos lugares como cor de texto genérica secundária (email do cliente, nome do profissional) — mapear para `#4a4a4a` **apenas** quando listado explicitamente numa task abaixo; senão, deixar como está (é só um cinza neutro do Tailwind, não uma cor de marca).

**Não mexer** (categorias distintas, sem equivalente no sistema novo, ou puramente decorativas): `#6d28d9` (status "reagendamento solicitado" — 4ª categoria distinta, sem token equivalente), `#c4a882` (texto de slot indisponível), sombras neutras baseadas em preto (`rgba(0,0,0,...)`, `rgba(24,32,27,...)`), disabled states cinza-esverdeados no botão de `/[slug]` (`#39433c`/`#303a33`/`#99a49c`).

---

## Task 1: Recolorir `BookingTokenActionCard.tsx`

**Files:**
- Modify: `frontend/app/components/BookingTokenActionCard.tsx`

Este componente é usado por `/confirmar/[token]` e `/cancelar/[token]` (ambos são wrappers finos de 10 linhas que só passam `mode="confirmar"`/`mode="cancelar"`, nada a mudar neles).

- [ ] **Step 1: Atualizar os mapas de cor no topo do arquivo**

Substituir:

```typescript
function labelStatus(status: PublicAgendamentoTokenResponse["status"]) {
  const mapa: Record<string, { label: string; color: string }> = {
    pendente:                 { label: "Pendente",                color: "#b45309" },
    confirmado:               { label: "Confirmado",              color: "#15803d" },
    cancelado:                { label: "Cancelado",               color: "#b91c1c" },
    reagendamento_solicitado: { label: "Reagendamento solicitado", color: "#6d28d9" },
  };
  return mapa[status] ?? { label: status, color: "#6b7280" };
}
```

Por:

```typescript
function labelStatus(status: PublicAgendamentoTokenResponse["status"]) {
  const mapa: Record<string, { label: string; color: string }> = {
    pendente:                 { label: "Pendente",                color: "#854d0e" },
    confirmado:               { label: "Confirmado",              color: "#166534" },
    cancelado:                { label: "Cancelado",               color: "#991b1b" },
    reagendamento_solicitado: { label: "Reagendamento solicitado", color: "#6d28d9" },
  };
  return mapa[status] ?? { label: status, color: "#6b7280" };
}
```

(Só `pendente`, `confirmado` e `cancelado` mudam, alinhando com `--warning`/`--success`/`--danger` do painel admin. `reagendamento_solicitado` e o fallback ficam iguais — são categorias sem equivalente no novo sistema.)

Substituir:

```typescript
const modeConfig = {
  confirmar: {
    titulo: "Confirmar presença",
    subtitulo: "Confirme que você comparecerá ao seu horário.",
    botao: "Confirmar presença",
    executar: confirmBookingByToken,
    sucessoMsg: "Presença confirmada! Até logo.",
    accentColor: "#15803d",
    accentBg: "#f0fdf4",
    accentText: "#14532d",
  },
  cancelar: {
    titulo: "Cancelar agendamento",
    subtitulo: "Não poderá comparecer? Cancele com antecedência.",
    botao: "Cancelar horário",
    executar: cancelBookingByToken,
    sucessoMsg: "Agendamento cancelado.",
    accentColor: "#b91c1c",
    accentBg: "#fff1f2",
    accentText: "#7f1d1d",
  },
  reagendar: {
    titulo: "Reagendar",
    subtitulo: "Solicite o reagendamento e escolha um novo horário.",
    botao: "Solicitar reagendamento",
    executar: requestRescheduleByToken,
    sucessoMsg: "Pedido de reagendamento registrado.",
    accentColor: "#c36b2d",
    accentBg: "#fff7ed",
    accentText: "#7c2d12",
  },
} satisfies Record<BookingActionMode, unknown>;
```

Por:

```typescript
const modeConfig = {
  confirmar: {
    titulo: "Confirmar presença",
    subtitulo: "Confirme que você comparecerá ao seu horário.",
    botao: "Confirmar presença",
    executar: confirmBookingByToken,
    sucessoMsg: "Presença confirmada! Até logo.",
    accentColor: "#166534",
    accentBg: "#f0fdf4",
    accentText: "#166534",
  },
  cancelar: {
    titulo: "Cancelar agendamento",
    subtitulo: "Não poderá comparecer? Cancele com antecedência.",
    botao: "Cancelar horário",
    executar: cancelBookingByToken,
    sucessoMsg: "Agendamento cancelado.",
    accentColor: "#991b1b",
    accentBg: "#fef2f2",
    accentText: "#991b1b",
  },
  reagendar: {
    titulo: "Reagendar",
    subtitulo: "Solicite o reagendamento e escolha um novo horário.",
    botao: "Solicitar reagendamento",
    executar: requestRescheduleByToken,
    sucessoMsg: "Pedido de reagendamento registrado.",
    accentColor: "#1e3a5f",
    accentBg: "#eaf0f5",
    accentText: "#142a44",
  },
} satisfies Record<BookingActionMode, unknown>;
```

(`confirmar`/`cancelar` agora usam exatamente `--success`/`--danger` do painel admin, com `accentColor` e `accentText` unificados no mesmo tom — antes eram dois verdes/vermelhos ligeiramente diferentes. `reagendar` deixa de usar terracota e passa a usar o azul-petróleo como "ação primária", com um fundo suave petróleo em vez de laranja.)

- [ ] **Step 2: Recolorir o JSX — wrapper externo e barra de marca**

Substituir:

```typescript
      style={{
        minHeight: "100vh",
        backgroundColor: "#f5efe7",
```

Por:

```typescript
      style={{
        minHeight: "100vh",
        backgroundColor: "#f6f8fb",
```

Substituir:

```typescript
        style={{
          width: "100%",
          backgroundColor: "#1a120b",
```

Por:

```typescript
        style={{
          width: "100%",
          backgroundColor: "#14283f",
```

Substituir:

```typescript
            backgroundColor: "#c36b2d",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <CalendarDays size={17} color="#ffffff" aria-hidden="true" />
        </div>
        <span style={{ color: "#f5efe7", fontWeight: 700, fontSize: 15, letterSpacing: "0.02em" }}>
```

Por:

```typescript
            backgroundColor: "#1e3a5f",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <CalendarDays size={17} color="#ffffff" aria-hidden="true" />
        </div>
        <span style={{ color: "#ffffff", fontWeight: 700, fontSize: 15, letterSpacing: "0.02em" }}>
```

- [ ] **Step 3: Recolorir o cabeçalho do card (gradiente)**

Substituir:

```typescript
        <div
          style={{
            background: "linear-gradient(135deg, #1a120b 0%, #3b1f0d 100%)",
            padding: "32px 32px 28px",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#f2c89a",
            }}
          >
            Email de agendamento
          </p>
          <h1
            style={{
              margin: "10px 0 6px",
              fontSize: 26,
              fontWeight: 800,
              color: "#ffffff",
              lineHeight: 1.2,
            }}
          >
            {config.titulo}
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: "#e8d5c0" }}>
            {config.subtitulo}
          </p>
        </div>
```

Por:

```typescript
        <div
          style={{
            background: "linear-gradient(135deg, #1e3a5f 0%, #122840 100%)",
            padding: "32px 32px 28px",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#d99b3f",
            }}
          >
            Email de agendamento
          </p>
          <h1
            style={{
              margin: "10px 0 6px",
              fontSize: 26,
              fontWeight: 800,
              color: "#ffffff",
              lineHeight: 1.2,
            }}
          >
            {config.titulo}
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: "rgba(255,255,255,0.75)" }}>
            {config.subtitulo}
          </p>
        </div>
```

- [ ] **Step 4: Recolorir loading e alerta de erro genérico**

Substituir:

```typescript
            <p style={{ color: "#9ca3af", fontSize: 14, margin: 0 }}>
              Carregando dados do agendamento...
            </p>
```

Por:

```typescript
            <p style={{ color: "#9a9a9a", fontSize: 14, margin: 0 }}>
              Carregando dados do agendamento...
            </p>
```

Substituir:

```typescript
              style={{
                backgroundColor: "#fff1f2",
                border: "1px solid #fecdd3",
                borderRadius: 12,
                padding: "12px 16px",
                marginBottom: 20,
                fontSize: 14,
                color: "#9f1239",
                fontWeight: 500,
              }}
            >
              {erro}
```

Por:

```typescript
              style={{
                backgroundColor: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 12,
                padding: "12px 16px",
                marginBottom: 20,
                fontSize: 14,
                color: "#991b1b",
                fontWeight: 500,
              }}
            >
              {erro}
```

(O bloco de sucesso logo abaixo usa `config.accentBg`/`config.accentColor`/`config.accentText` dinamicamente — já resolvido pelo Step 1, não precisa editar aqui.)

- [ ] **Step 5: Recolorir os detalhes do agendamento**

Substituir:

```typescript
              <div
                style={{
                  backgroundColor: "#faf7f4",
                  borderRadius: 14,
```

Por:

```typescript
              <div
                style={{
                  backgroundColor: "#f0f2f5",
                  borderRadius: 14,
```

Substituir (4 ocorrências idênticas — usar replace_all):

```
color: "#c36b2d"
```

Por (nos 4 labels "Cliente"/"Status"/"Serviço"/"Horário" — confirme que são exatamente estas 4 ocorrências antes de aplicar; NÃO mexer em outras ocorrências de `#c36b2d` que já foram tratadas nos steps anteriores):

```
color: "#d99b3f"
```

Substituir (3 ocorrências — `cliente_nome`, `servico_nome`, `data_hora_inicio` — usar replace_all neste escopo específico):

```
color: "#1a120b"
```

Por:

```
color: "#1a1a1a"
```

- [ ] **Step 6: Recolorir os links secundários**

Substituir (2 ocorrências idênticas — link "Escolher novo horário" e link "Voltar para o site" — usar replace_all):

```
border: "1.5px solid #e5d5c5",
                        backgroundColor: "transparent",
                        color: "#3b1f0d",
```

Por:

```
border: "1.5px solid #e5e9ee",
                        backgroundColor: "transparent",
                        color: "#142a44",
```

- [ ] **Step 7: Recolorir o rodapé**

Substituir:

```typescript
      <p style={{ fontSize: 12, color: "#a18070", marginBottom: 32 }}>
```

Por:

```typescript
      <p style={{ fontSize: 12, color: "#9a9a9a", marginBottom: 32 }}>
```

- [ ] **Step 8: Rodar o build**

Run: `cd frontend && npm run build`
Expected: sem erros.

- [ ] **Step 9: Verificar visualmente**

Run: `cd frontend && npm run start`, então abrir `/confirmar/algum-token-de-teste` e `/cancelar/algum-token-de-teste` (ou usar um token real de um agendamento de teste, se disponível) — confirmar barra superior e cabeçalho do card em azul-petróleo com gradiente, labels em âmbar, botão de ação em petróleo (confirmar/reagendar) ou vermelho (cancelar).

- [ ] **Step 10: Commit**

```bash
git add frontend/app/components/BookingTokenActionCard.tsx
git commit -m "feat(design): recolorir BookingTokenActionCard para paleta petroleo/ambar"
```

## Context

Este é o Task 1 de um plano de 4 tasks (`docs/superpowers/plans/2026-07-27-visual-redesign-public-pages-plan.md`), a continuação do Plano 1 (painel admin, já concluído). `BookingTokenActionCard.tsx` é usado por `/confirmar/[token]` e `/cancelar/[token]` (wrappers de 10 linhas, não precisam de mudança). Ele usa `style={{}}` inline do React em vez de CSS Modules ou variáveis CSS — por isso as trocas são de string literal, não de variável.

---

## Task 2: Recolorir `reagendar/[token]/page.tsx`

**Files:**
- Modify: `frontend/app/reagendar/[token]/page.tsx`

Este arquivo é quase um "gêmeo" do `BookingTokenActionCard.tsx` (mesma barra de marca, mesmo cabeçalho em gradiente, mesmo rodapé), mas é uma página standalone com lógica própria de escolha de novo horário — não reutiliza o componente do Task 1.

- [ ] **Step 1: Recolorir os estilos compartilhados (`inputStyle` / `labelTextStyle`)**

Substituir:

```typescript
  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 10,
    border: "1.5px solid #e5d5c5",
    backgroundColor: "#faf7f4",
    fontSize: 14,
    color: "#1a120b",
    outline: "none",
    boxSizing: "border-box",
  };

  const labelStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: 5,
  };

  const labelTextStyle: React.CSSProperties = {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.14em",
    textTransform: "uppercase",
    color: "#c36b2d",
    margin: 0,
  };
```

Por:

```typescript
  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 10,
    border: "1.5px solid #e5e9ee",
    backgroundColor: "#f0f2f5",
    fontSize: 14,
    color: "#1a1a1a",
    outline: "none",
    boxSizing: "border-box",
  };

  const labelStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: 5,
  };

  const labelTextStyle: React.CSSProperties = {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.14em",
    textTransform: "uppercase",
    color: "#d99b3f",
    margin: 0,
  };
```

- [ ] **Step 2: Recolorir o wrapper externo e a barra de marca**

Substituir:

```typescript
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#f5efe7",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Top brand bar */}
      <div
        style={{
          width: "100%",
          backgroundColor: "#1a120b",
          padding: "14px 24px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            backgroundColor: "#c36b2d",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <CalendarDays size={17} color="#ffffff" aria-hidden="true" />
        </div>
        <span style={{ color: "#f5efe7", fontWeight: 700, fontSize: 15, letterSpacing: "0.02em" }}>
          {PRODUCT_NAME}
        </span>
      </div>
```

Por:

```typescript
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#f6f8fb",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Top brand bar */}
      <div
        style={{
          width: "100%",
          backgroundColor: "#14283f",
          padding: "14px 24px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            backgroundColor: "#1e3a5f",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <CalendarDays size={17} color="#ffffff" aria-hidden="true" />
        </div>
        <span style={{ color: "#ffffff", fontWeight: 700, fontSize: 15, letterSpacing: "0.02em" }}>
          {PRODUCT_NAME}
        </span>
      </div>
```

- [ ] **Step 3: Recolorir o cabeçalho do card (gradiente)**

Substituir:

```typescript
        <div
          style={{
            background: "linear-gradient(135deg, #1a120b 0%, #3b1f0d 100%)",
            padding: "32px 32px 28px",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#f2c89a",
            }}
          >
            Email de agendamento
          </p>
          <h1
            style={{
              margin: "10px 0 6px",
              fontSize: 26,
              fontWeight: 800,
              color: "#ffffff",
              lineHeight: 1.2,
            }}
          >
            Escolher novo horário
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: "#e8d5c0" }}>
            Selecione data e horário para seu reagendamento.
          </p>
        </div>
```

Por:

```typescript
        <div
          style={{
            background: "linear-gradient(135deg, #1e3a5f 0%, #122840 100%)",
            padding: "32px 32px 28px",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#d99b3f",
            }}
          >
            Email de agendamento
          </p>
          <h1
            style={{
              margin: "10px 0 6px",
              fontSize: 26,
              fontWeight: 800,
              color: "#ffffff",
              lineHeight: 1.2,
            }}
          >
            Escolher novo horário
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: "rgba(255,255,255,0.75)" }}>
            Selecione data e horário para seu reagendamento.
          </p>
        </div>
```

- [ ] **Step 4: Recolorir loading e o alerta de "agendamento não encontrado"**

Substituir:

```typescript
          {loadingBooking && (
            <p style={{ color: "#9ca3af", fontSize: 14, margin: 0 }}>
              Carregando agendamento...
            </p>
          )}

          {!loadingBooking && !booking && (
            <div
              style={{
                backgroundColor: "#fff1f2",
                border: "1px solid #fecdd3",
                borderRadius: 12,
                padding: "12px 16px",
                fontSize: 14,
                color: "#9f1239",
              }}
            >
              {erro ?? "Agendamento não encontrado."}
            </div>
          )}
```

Por:

```typescript
          {loadingBooking && (
            <p style={{ color: "#9a9a9a", fontSize: 14, margin: 0 }}>
              Carregando agendamento...
            </p>
          )}

          {!loadingBooking && !booking && (
            <div
              style={{
                backgroundColor: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 12,
                padding: "12px 16px",
                fontSize: 14,
                color: "#991b1b",
              }}
            >
              {erro ?? "Agendamento não encontrado."}
            </div>
          )}
```

- [ ] **Step 5: Recolorir os detalhes do agendamento atual**

Substituir:

```typescript
              <div
                style={{
                  backgroundColor: "#faf7f4",
                  borderRadius: 14,
                  padding: "20px 22px",
                  marginBottom: 24,
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "16px 24px",
                }}
              >
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Cliente</p>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#1a120b" }}>
                    {booking.cliente_nome}
                  </p>
                </div>
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Horário atual</p>
                  <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: "#1a120b", lineHeight: 1.4 }}>
                    {formatarDataHora(booking.data_hora_inicio)}
                  </p>
                </div>
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Serviço</p>
                  <p style={{ margin: 0, fontSize: 14, color: "#1a120b" }}>{booking.servico_nome}</p>
                </div>
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Profissional</p>
                  <p style={{ margin: 0, fontSize: 14, color: "#1a120b" }}>{booking.barbeiro_nome}</p>
                </div>
              </div>
```

Por:

```typescript
              <div
                style={{
                  backgroundColor: "#f0f2f5",
                  borderRadius: 14,
                  padding: "20px 22px",
                  marginBottom: 24,
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "16px 24px",
                }}
              >
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Cliente</p>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#1a1a1a" }}>
                    {booking.cliente_nome}
                  </p>
                </div>
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Horário atual</p>
                  <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: "#1a1a1a", lineHeight: 1.4 }}>
                    {formatarDataHora(booking.data_hora_inicio)}
                  </p>
                </div>
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Serviço</p>
                  <p style={{ margin: 0, fontSize: 14, color: "#1a1a1a" }}>{booking.servico_nome}</p>
                </div>
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Profissional</p>
                  <p style={{ margin: 0, fontSize: 14, color: "#1a1a1a" }}>{booking.barbeiro_nome}</p>
                </div>
              </div>
```

- [ ] **Step 6: Recolorir os alertas de sucesso / erro / cancelado**

Substituir:

```typescript
              {sucesso && (
                <div
                  style={{
                    backgroundColor: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: 12,
                    padding: "12px 16px",
                    marginBottom: 20,
                    fontSize: 14,
                    color: "#14532d",
                    fontWeight: 600,
                  }}
                >
                  ✓ {sucesso}
                </div>
              )}

              {erro && !sucesso && (
                <div
                  style={{
                    backgroundColor: "#fff1f2",
                    border: "1px solid #fecdd3",
                    borderRadius: 12,
                    padding: "12px 16px",
                    marginBottom: 20,
                    fontSize: 14,
                    color: "#9f1239",
                  }}
                >
                  {erro}
                </div>
              )}

              {booking.status === "cancelado" && (
                <div
                  style={{
                    backgroundColor: "#fff1f2",
                    border: "1px solid #fecdd3",
                    borderRadius: 12,
                    padding: "12px 16px",
                    marginBottom: 20,
                    fontSize: 14,
                    color: "#9f1239",
                  }}
                >
                  Este agendamento foi cancelado e não pode ser reagendado.
                </div>
              )}
```

Por:

```typescript
              {sucesso && (
                <div
                  style={{
                    backgroundColor: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: 12,
                    padding: "12px 16px",
                    marginBottom: 20,
                    fontSize: 14,
                    color: "#166534",
                    fontWeight: 600,
                  }}
                >
                  ✓ {sucesso}
                </div>
              )}

              {erro && !sucesso && (
                <div
                  style={{
                    backgroundColor: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: 12,
                    padding: "12px 16px",
                    marginBottom: 20,
                    fontSize: 14,
                    color: "#991b1b",
                  }}
                >
                  {erro}
                </div>
              )}

              {booking.status === "cancelado" && (
                <div
                  style={{
                    backgroundColor: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: 12,
                    padding: "12px 16px",
                    marginBottom: 20,
                    fontSize: 14,
                    color: "#991b1b",
                  }}
                >
                  Este agendamento foi cancelado e não pode ser reagendado.
                </div>
              )}
```

- [ ] **Step 7: Recolorir o texto de "carregando horários"**

Substituir:

```typescript
                  {loadingSlots ? (
                    <p style={{ color: "#9ca3af", fontSize: 13, marginBottom: 20 }}>
                      Carregando horários...
                    </p>
```

Por:

```typescript
                  {loadingSlots ? (
                    <p style={{ color: "#9a9a9a", fontSize: 13, marginBottom: 20 }}>
                      Carregando horários...
                    </p>
```

- [ ] **Step 8: Recolorir os botões de horário (time slots)**

Substituir:

```typescript
                          style={{
                            padding: "10px 4px",
                            borderRadius: 10,
                            border: "1.5px solid",
                            borderColor: !slot.disponivel
                              ? "#e5d5c5"
                              : horaInicio === slot.hora
                                ? "#c36b2d"
                                : "#e5d5c5",
                            backgroundColor: !slot.disponivel
                              ? "#faf7f4"
                              : horaInicio === slot.hora
                                ? "#c36b2d"
                                : "#ffffff",
                            color: !slot.disponivel
                              ? "#c4a882"
                              : horaInicio === slot.hora
                                ? "#ffffff"
                                : "#1a120b",
```

Por:

```typescript
                          style={{
                            padding: "10px 4px",
                            borderRadius: 10,
                            border: "1.5px solid",
                            borderColor: !slot.disponivel
                              ? "#e5e9ee"
                              : horaInicio === slot.hora
                                ? "#1e3a5f"
                                : "#e5e9ee",
                            backgroundColor: !slot.disponivel
                              ? "#f0f2f5"
                              : horaInicio === slot.hora
                                ? "#1e3a5f"
                                : "#ffffff",
                            color: !slot.disponivel
                              ? "#c4a882"
                              : horaInicio === slot.hora
                                ? "#ffffff"
                                : "#1a1a1a",
```

- [ ] **Step 9: Recolorir "nenhum horário disponível" e o botão de submeter**

Substituir:

```typescript
                  ) : lookup ? (
                    <p style={{ color: "#9ca3af", fontSize: 13, marginBottom: 20 }}>
                      Nenhum horário disponível nesta data.
                    </p>
                  ) : null}

                  <button
                    type="button"
                    disabled={submitting || !horaInicio}
                    onClick={onSubmit}
                    style={{
                      width: "100%",
                      padding: "14px 20px",
                      borderRadius: 12,
                      border: "none",
                      backgroundColor: "#c36b2d",
                      color: "#ffffff",
```

Por:

```typescript
                  ) : lookup ? (
                    <p style={{ color: "#9a9a9a", fontSize: 13, marginBottom: 20 }}>
                      Nenhum horário disponível nesta data.
                    </p>
                  ) : null}

                  <button
                    type="button"
                    disabled={submitting || !horaInicio}
                    onClick={onSubmit}
                    style={{
                      width: "100%",
                      padding: "14px 20px",
                      borderRadius: 12,
                      border: "none",
                      backgroundColor: "#1e3a5f",
                      color: "#ffffff",
```

- [ ] **Step 10: Recolorir o link "Voltar" e o rodapé**

Substituir:

```typescript
              {(sucesso || booking.status === "cancelado") && (
                <Link
                  href={linkEstabelecimento}
                  style={{
                    display: "block",
                    textAlign: "center",
                    marginTop: 12,
                    padding: "13px 20px",
                    borderRadius: 12,
                    border: "1.5px solid #e5d5c5",
                    color: "#3b1f0d",
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  Voltar para o site do estabelecimento →
                </Link>
              )}
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <p style={{ fontSize: 12, color: "#a18070", marginBottom: 32 }}>
        Agendamento por {PRODUCT_NAME}
      </p>
```

Por:

```typescript
              {(sucesso || booking.status === "cancelado") && (
                <Link
                  href={linkEstabelecimento}
                  style={{
                    display: "block",
                    textAlign: "center",
                    marginTop: 12,
                    padding: "13px 20px",
                    borderRadius: 12,
                    border: "1.5px solid #e5e9ee",
                    color: "#142a44",
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  Voltar para o site do estabelecimento →
                </Link>
              )}
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <p style={{ fontSize: 12, color: "#9a9a9a", marginBottom: 32 }}>
        Agendamento por {PRODUCT_NAME}
      </p>
```

- [ ] **Step 11: Rodar o build**

Run: `cd frontend && npm run build`
Expected: sem erros.

- [ ] **Step 12: Verificar visualmente**

Run: `cd frontend && npm run start`, abrir `/reagendar/algum-token-de-teste` — confirmar a mesma barra/cabeçalho petróleo do Task 1, botões de horário com seleção em petróleo, botão de submeter em petróleo.

- [ ] **Step 13: Commit**

```bash
git add "frontend/app/reagendar/[token]/page.tsx"
git commit -m "feat(design): recolorir pagina de reagendamento para paleta petroleo/ambar"
```

## Context

Este é o Task 2 do plano. Este arquivo (`frontend/app/reagendar/[token]/page.tsx`, 533 linhas) compartilha ~17 valores de cor idênticos com `BookingTokenActionCard.tsx` (Task 1) — mesma barra de marca, mesmo gradiente de cabeçalho, mesmo rodapé — então a tradução de cor é a mesma, só que reaplicada nos locais próprios deste arquivo (que tem sua própria lógica de escolha de horário, não reutiliza o componente do Task 1).

---

## Task 3: Recolorir `[slug]/page.module.css`

**Files:**
- Modify: `frontend/app/[slug]/page.module.css`

Esta é a página pública de agendamento (a real — `/agendar/[estabelecimentoId]` só redireciona pra cá). Hoje usa uma paleta verde/dourado própria, isolada do resto do sistema (nenhuma variável CSS). Vamos trocar pra petróleo/âmbar, seguindo o mapa de cores no topo deste documento.

- [ ] **Step 1: Fundo de página, marca e badge de segurança**

- `.page` — `background: #f2f5f1;` → `background: #f6f8fb;`; `color: #18201b;` → `color: #1a1a1a;`
- `.brandMark` — `background: #18201b;` → `background: #1e3a5f;`; a cor do ícone/texto `#f6bc2f` → `#d99b3f`; `box-shadow: rgba(24, 32, 27, 0.16)` fica igual (sombra neutra)
- `.brandIdentity h1` — `color: #18201b;` → `color: #1a1a1a;`
- `.brandSubtitle` — `color: #68736b;` → `color: #4a4a4a;`
- `.eyebrow, .summaryHeading p` — `color: #4d6958;` → `color: #4a4a4a;`
- `.secureBadge` — `border: 1px solid #d5ddd6;` → `border: 1px solid #e5e9ee;`; `color: #365c45;` → `color: #166534;` (fundo `#ffffff` fica igual)

- [ ] **Step 2: Formulário e campos**

- `.formPanel` — `border: 1px solid #dce3dd;` → `border: 1px solid #e5e9ee;`; `box-shadow: rgba(24, 32, 27, 0.07)` fica igual (fundo `#ffffff` fica igual)
- `.fieldLabel` — `color: #344139;` → `color: #1a1a1a;`
- `.stepSection` — `border-bottom: ...#e5eae6;` → `border-bottom: ...#e5e9ee;`
- `.stepHeader p` — `color: #748078;` → `color: #4a4a4a;`
- `.stepIndicator` — `border: ...#cad4cc;` → `border: ...#e5e9ee;`; `background: #f7f9f7;` → `background: #f0f2f5;`; `color: #526158;` → `color: #4a4a4a;`
- `.stepComplete` — `border-color: #2f7d52;` → `border-color: #166534;`; `background: #2f7d52;` → `background: #166534;` (texto `#ffffff` fica igual)
- `.control` — `border: ...#ccd6ce;` → `border: ...#e5e9ee;`; `color: #1f2922;` → `color: #1a1a1a;` (texto `#ffffff` de outro contexto, se houver, fica igual)
- `.controlWrap > svg` — `color: #718078;` → `color: #4a4a4a;`
- `.control:hover` — `border-color: #aebdb2;` → `border-color: #9a9a9a;`
- `.control:focus` — `border-color: #28794d;` → `border-color: #1e3a5f;`; `box-shadow: rgba(40, 121, 77, 0.13)` → `box-shadow: rgba(30, 58, 95, 0.16)`
- `.control::placeholder` — `color: #9aa49d;` → `color: #9a9a9a;`
- `.scheduleHeader` — `color: #344139;` → `color: #1a1a1a;`

- [ ] **Step 3: Faixa de serviço e legenda**

- `.serviceStrip` — `border-left: ...#e9b126;` → `border-left: ...#d99b3f;`; `background: #fbfaf4;` → `background: #fdf3e2;`; `color: #273229;` → `color: #1a1a1a;`
- `.serviceStrip small` — `color: #778179;` → `color: #4a4a4a;`
- `.serviceIcon` — `background: #f7e9b9;` → `background: #fdf3e2;`; `color: #725513;` → `color: #8a5f1f;`
- `.legend` — `color: #7b867f;` → `color: #4a4a4a;`

- [ ] **Step 4: Grade de horários (slots)**

- `.availableDot` — `background: #32935e;` → `background: #166534;`
- `.unavailableDot` — fica igual (`#b6beb8`, cinza neutro)
- `.slot` — `border: ...#b7d7c2;` → `border: ...#bbf7d0;`; `background: #f4fbf6;` → `background: #f0fdf4;`; `color: #1d6b41;` → `color: #166534;`
- `.slot:hover:not(:disabled)` — `border-color: #479a68;` → `border-color: #4a9d68;`; `background: #e6f5eb;` → `background: #e3f8ea;`
- `.slot:focus-visible` — `outline: rgba(40, 121, 77, 0.2)` → `outline: rgba(22, 101, 52, 0.2)`
- `.slotSelected, .slotSelected:hover` — `border-color: #1f5e3b;` → `border-color: #1e3a5f;`; `background: #1f5e3b;` → `background: #1e3a5f;` (texto `#ffffff` fica igual)
- `.slotUnavailable` — `border-color: #e1e5e2;` → `border-color: #e5e9ee;`; `background: #f3f5f3;` → `background: #f0f2f5;`; `color: #9da69f;` → `color: #9a9a9a;`
- `.slotSkeleton` — `background: #edf1ed;` → `background: #f0f2f5;`
- `.emptySlots` — `border: dashed ...#cfd7d1;` → `border: dashed ...#e5e9ee;`; `color: #68746c;` → `color: #4a4a4a;`

- [ ] **Step 5: Resumo do agendamento (painel escuro) e aviso de pagamento**

- `.summaryPanel` — `background: #18201b;` → `background: #142a44;`; `border: ...#2b3930;` → `border: ...rgba(255,255,255,0.10);`; `box-shadow: rgba(24, 32, 27, 0.17)` fica igual; `color: #f7faf7;` fica igual (quase branco, sem mudança)
- `.summaryHeading h2` — `color: #ffffff;` fica igual
- `.summaryHeading p` — `color: #e9b842;` → `color: #d99b3f;`
- `.summaryHeading, .summaryList` — `border-bottom: rgba(255, 255, 255, 0.11)` fica igual (as duas ocorrências)
- `.summaryItem > span` — `background: rgba(255, 255, 255, 0.08)` fica igual; `color: #f3c456;` → `color: #d99b3f;`
- `.summaryItem small` — fica igual (`#9fad9f`, neutro claro sobre fundo escuro)
- `.summaryItem strong` — fica igual (`#f5f7f5`, quase branco)
- `.summaryItem .pendingValue` — fica igual (`#aeb8b0`, neutro)
- `.totalRow span` — fica igual (`#bdc8bf`, neutro)
- `.totalRow strong` — fica igual (`#ffffff`)
- `.paymentNotice` — `border: rgba(246, 188, 47, 0.33)` → `border: rgba(217, 155, 63, 0.33)`; `background: rgba(246, 188, 47, 0.11)` → `background: rgba(217, 155, 63, 0.11)`; `color: #f5d990;` → `color: #d99b3f;`
- `.paymentNotice strong` — `color: #ffe6a7;` → `color: #d99b3f;`

- [ ] **Step 6: Botão de envio (submitButton)**

- `.submitButton` — `border-color: #f6bc2f;` → `border-color: #d99b3f;`; `background: #f6bc2f;` → `background: #d99b3f;` (texto `#222a24` fica igual — já é escuro o bastante pra contraste)
- `.submitButton:hover:not(:disabled)` — `border-color: #ffd05d;` → `border-color: #e2ac57;`; `background: #ffd05d;` → `background: #e2ac57;`
- `.submitButton:focus-visible` — `outline: rgba(246, 188, 47, 0.28)` → `outline: rgba(217, 155, 63, 0.28)`
- `.submitButton:disabled` — fica igual (`#39433c`/`#303a33`/`#99a49c` — estado desabilitado neutro, sem necessidade de seguir a marca)

- [ ] **Step 7: Painel de estado (loading/erro/sucesso) e alertas**

- `.statePanel` — fundo `#ffffff` fica igual; `border: ...#dce3dd;` → `border: ...#e5e9ee;`; `box-shadow: rgba(24, 32, 27, 0.08)` fica igual
- `.statePanel strong` — `color: #18201b;` → `color: #1a1a1a;`
- `.statePanel p` — `color: #758078;` → `color: #4a4a4a;`
- `.errorAlert`/`.successAlert` — **ficam iguais, sem mudança** (ver nota de correção abaixo).

**Correção pós-implementação (2026-07-27):** a versão original deste plano dizia pra trocar `.errorAlert`/`.successAlert` pra cores sólidas claras, assumindo que `.statePanel` (fundo branco) era o pai desses elementos. Isso estava errado — checando `frontend/app/[slug]/page.tsx`, `.errorAlert`/`.successAlert` na verdade renderizam dentro de `.feedback`, dentro de `<aside className={styles.summaryPanel}>` (fundo escuro `#142a44`), igual ao `.paymentNotice` que já ficava corretamente com cores translúcidas no mesmo painel. A implementação seguiu a instrução original e converteu pra cores sólidas claras, o que ficou visualmente quebrado (uma caixa clara boiando no meio do painel escuro) — encontrado e corrigido na revisão de qualidade de código antes do merge, revertendo `.errorAlert`/`.successAlert` pros valores translúcidos originais (que já estavam corretos pro fundo escuro).

- [ ] **Step 8: Rodar o build**

Run: `cd frontend && npm run build`
Expected: sem erros.

- [ ] **Step 9: Verificar visualmente**

Run: `cd frontend && npm run start`, abrir `/algum-slug-de-teste` (um estabelecimento de teste existente) — percorrer o fluxo: escolher serviço, ver a grade de horários (disponível em verde-sucesso, selecionado em petróleo), preencher o formulário, ver o resumo do agendamento (painel escuro petróleo com valores em âmbar), e confirmar. Checar também os estados de erro/sucesso se conseguir forçá-los.

- [ ] **Step 10: Commit**

```bash
git add "frontend/app/[slug]/page.module.css"
git commit -m "feat(design): recolorir pagina publica de agendamento (verde/dourado -> petroleo/ambar)"
```

## Context

Este é o Task 3 do plano — o arquivo isolado mais importante (a página pública de agendamento de verdade, 723 linhas de CSS, ~90 declarações de cor). Ele não compartilha nenhuma cor de marca com os arquivos do Task 1/2 (são paletas completamente separadas hoje — verde/dourado aqui vs. marrom/terracota lá), então este task é independente dos anteriores. `frontend/app/[slug]/page.tsx` (o componente React) não tem nenhuma cor inline — todo o estilo vem deste módulo CSS, então não precisa editar o `.tsx`.

---

## Task 4: Verificação final

**Files:** nenhum (apenas verificação — se gerar diffs de código, é sinal de que algo passou batido nas tasks anteriores)

- [ ] **Step 1: Build de produção completo**

Run: `cd frontend && npm run build`
Expected: sem erros.

- [ ] **Step 2: `tsc` isolado**

Run: `cd frontend && npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 3: Grep de sanidade — confirmar que as cores antigas sumiram**

```bash
cd frontend
grep -rn "c36b2d\|1a120b\|3b1f0d\|e5d5c5\|f2c89a\|e8d5c0\|f5efe7" app/components/BookingTokenActionCard.tsx "app/reagendar/[token]/page.tsx"
grep -rn "18201b\|f2f5f1\|f6bc2f\|2f7d52\|28794d\|32935e\|1f5e3b" "app/[slug]/page.module.css"
```

Expected: nenhuma ocorrência (ambos os comandos retornam vazio). Se algo aparecer, é uma cor que passou batido numa task anterior — voltar e corrigir antes de prosseguir.

- [ ] **Step 4: Passada visual manual**

Run: `cd frontend && npm run start`, então visitar (com um estabelecimento/token de teste real ou simulado):
- `/[slug-de-teste]` — fluxo completo de agendamento público
- `/confirmar/[token-de-teste]`
- `/cancelar/[token-de-teste]`
- `/reagendar/[token-de-teste]`

Confirmar visualmente: paleta petróleo/âmbar consistente nas 4 telas, sem nenhum resquício de verde/dourado ou marrom/terracota antigos, textos legíveis (contraste ok), botões de ação com a cor certa (petróleo para confirmar/reagendar, vermelho para cancelar).

- [ ] **Step 5: Backend inalterado**

Run: `cd backend && python -m pytest -q`
Expected: mesma contagem de testes passando de antes (349 ou o número atual), 0 falhas — confirma que este plano, sendo 100% frontend, não afetou o backend.

- [ ] **Step 6: Relatar resultado**

Se tudo passou: registrar que a verificação visual foi manual (não existe suíte de regressão visual automatizada). Se algo destoar, anotar a tela e o elemento específico como follow-up, sem corrigir dentro desta task de verificação.
