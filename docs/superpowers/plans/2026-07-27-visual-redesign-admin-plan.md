# Redesign Visual — Painel Admin (Plano 1 de 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar o novo sistema de design (paleta azul-petróleo + âmbar, tipografia Inter, navegação lateral, novo logo) em todo o painel administrativo do Hagendei (login, painel, agenda, gestão, dashboard, configurações, admin).

**Architecture:** A maior parte do painel já usa variáveis CSS centralizadas (`--accent`, `--ink`, `--line`, etc. em `frontend/app/globals.css`), então trocar os valores dessas variáveis já re-tema a maioria dos componentes automaticamente. O trabalho manual concentra-se em: (1) uma variável CSS que é sobrescrita em runtime por tenant (`useTenantTheme`) e precisa do novo valor padrão; (2) a navegação, que muda de estrutura (topo → lateral), exigindo componentes novos; (3) a tela de login, que usa cores fixas em vez de variáveis (por design — não reage a tema claro/escuro) e precisa de edição literal.

**Tech Stack:** Next.js 16 (App Router), TypeScript, CSS Modules, `next/font/google`, lucide-react.

**Nota de escopo:** a spec original previa a barra lateral colapsar num drawer com botão hamburguer em mobile. Este plano simplifica para manter a barra de ícones sempre visível (só mais estreita em telas pequenas) — evita a complexidade de estado aberto/fechado sem perder usabilidade, já que uma barra de 56-64px de ícones já é compacta o bastante para não precisar esconder. Documentado aqui para review.

---

## Task 1: Paleta e tipografia — tokens em `globals.css`

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Trocar a paleta light mode (linhas 1-42)**

Substituir o bloco de tipografia + paleta light mode inteiro:

```css
/* ─── TIPOGRAFIA ─────────────────────────────────────────── */
:root {
  --font-display: var(--font-sans), system-ui, sans-serif;
  --font-body: var(--font-sans), system-ui, sans-serif;
}

/* ─── PALETA LIGHT MODE ──────────────────────────────────── */
:root {
  --ink:          #1a1a1a;
  --ink-muted:    #4a4a4a;
  --ink-subtle:   #9a9a9a;
  --canvas:       #f6f8fb;
  --surface:      #ffffff;
  --surface-alt:  #f0f2f5;
  --line:         #e5e9ee;
  --overlay:      rgba(0,0,0,0.48);

  --accent:       #1e3a5f;
  --accent-dark:  #142a44;
  --accent-soft:  #eaf0f5;
  --accent-ring:  rgba(30,58,95,0.16);

  --warm:         #d99b3f;
  --warm-soft:    #fdf3e2;

  --success:      #166534;
  --success-soft: #f0fdf4;
  --success-line: #bbf7d0;
  --warning:      #854d0e;
  --warning-soft: #fefce8;
  --warning-line: #fde68a;
  --danger:       #991b1b;
  --danger-soft:  #fef2f2;
  --danger-line:  #fecaca;

  --radius-sm:  6px;
  --radius-md:  8px;
  --radius-lg:  12px;
  --radius-xl:  14px;
  --radius-2xl: 16px;

  --shadow-sm:  0 1px 4px rgba(0,0,0,0.06);
  --shadow-md:  0 4px 16px rgba(0,0,0,0.08);
  --shadow-lg:  0 8px 32px rgba(0,0,0,0.10);
}
```

- [ ] **Step 2: Trocar a paleta dark mode**

Substituir o bloco `[data-theme="dark"]`:

```css
/* ─── PALETA DARK MODE ───────────────────────────────────── */
[data-theme="dark"] {
  --ink:          #f0f0ee;
  --ink-muted:    #b0b0ae;
  --ink-subtle:   #707070;
  --canvas:       #141414;
  --surface:      #1e1e1c;
  --surface-alt:  #282826;
  --line:         rgba(255,255,255,0.10);
  --overlay:      rgba(0,0,0,0.68);

  --accent:       #5b84ad;
  --accent-dark:  #4d7aa8;
  --accent-soft:  rgba(30,58,95,0.35);
  --accent-ring:  rgba(91,132,173,0.20);

  --warm:         #e0ac5f;
  --warm-soft:    rgba(217,155,63,0.18);

  --success:      #4ade80;
  --success-soft: rgba(74,222,128,0.12);
  --success-line: rgba(74,222,128,0.25);
  --warning:      #fbbf24;
  --warning-soft: rgba(251,191,36,0.12);
  --warning-line: rgba(251,191,36,0.25);
  --danger:       #f87171;
  --danger-soft:  rgba(248,113,113,0.12);
  --danger-line:  rgba(248,113,113,0.25);
}
```

- [ ] **Step 3: Corrigir o botão sólido em dark mode pra usar o novo azul-petróleo**

Encontrar este bloco (mais abaixo no arquivo, perto de `.btn-outline-accent`):

```css
[data-theme="dark"] .btn-primary,
[data-theme="dark"] .btn-accent {
  background: #4f46e5;
  color: #ffffff;
}
```

Substituir por:

```css
[data-theme="dark"] .btn-primary,
[data-theme="dark"] .btn-accent {
  background: #1e3a5f;
  color: #ffffff;
}
```

(Motivo: em dark mode os botões sólidos usam uma cor fixa mais forte que `var(--accent)` — que em dark mode é um tom claro pensado pra texto/borda, não pra preencher um botão com texto branco em cima. Antes usava o indigo antigo hardcoded; agora usa o petróleo do light mode, que tem contraste alto o bastante com texto branco.)

- [ ] **Step 4: Trocar o anel de foco do input de indigo pra petróleo**

Encontrar:

```css
.input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(79,70,229,0.14);
}
```

Substituir por:

```css
.input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}
```

- [ ] **Step 5: Rodar o build do frontend pra confirmar que não quebrou nada**

Run: `cd frontend && npm run build`
Expected: build conclui sem erros de TypeScript/lint relacionados a `globals.css` (arquivo CSS não é checado por tsc, mas o build do Next processa o CSS e falharia em erro de sintaxe).

- [ ] **Step 6: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat(design): nova paleta azul-petroleo + ambar em globals.css"
```

---

## Task 2: Corrigir a cor padrão do tema por tenant

**Contexto crítico:** `useTenantTheme` roda em toda página autenticada e sobrescreve `--accent` via `style.setProperty` no `<html>` — isso tem prioridade sobre o valor definido em `globals.css`. O fallback hoje é `#d4930a` (dourado antigo), não o indigo do CSS. Sem esse fix, a nova paleta do Task 1 nunca aparece de verdade pra nenhum usuário logado sem cor customizada.

**Files:**
- Modify: `frontend/hooks/useTenantTheme.ts`

- [ ] **Step 1: Trocar o fallback padrão**

Arquivo completo atual:

```typescript
"use client";

import { useEffect } from "react";
import { useAuthSession } from "@/services/auth";

const DEFAULT_ACCENT = "#d4930a";
const DEFAULT_BG = "#ffffff";

export function useTenantTheme() {
  const session = useAuthSession();

  useEffect(() => {
    const accent = session?.accentColor || DEFAULT_ACCENT;
    const bg = session?.bgColor || DEFAULT_BG;

    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--accent-tenant", accent);
    document.documentElement.style.setProperty("--bg-tenant", bg);
  }, [session?.accentColor, session?.bgColor]);
}
```

Substituir por:

```typescript
"use client";

import { useEffect } from "react";
import { useAuthSession } from "@/services/auth";

const DEFAULT_ACCENT = "#1e3a5f";
const DEFAULT_BG = "#ffffff";

export function useTenantTheme() {
  const session = useAuthSession();

  useEffect(() => {
    const accent = session?.accentColor || DEFAULT_ACCENT;
    const bg = session?.bgColor || DEFAULT_BG;

    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--accent-tenant", accent);
    document.documentElement.style.setProperty("--bg-tenant", bg);
  }, [session?.accentColor, session?.bgColor]);
}
```

(Tenants que já customizaram a própria cor em `/configuracoes` continuam vendo a cor deles — só o padrão pra quem nunca customizou muda.)

- [ ] **Step 2: Commit**

```bash
git add frontend/hooks/useTenantTheme.ts
git commit -m "fix(design): fallback de accent do tenant usa o novo azul-petroleo"
```

---

## Task 3: Trocar tipografia pra Inter

**Files:**
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Trocar os imports e a configuração de fonte**

Substituir:

```typescript
import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Jost } from "next/font/google";
import "./globals.css";
import AppShell from "./components/AppShell";
import { ThemeProvider } from "./components/ThemeProvider";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const jost = Jost({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});
```

Por:

```typescript
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import AppShell from "./components/AppShell";
import { ThemeProvider } from "./components/ThemeProvider";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-sans",
  display: "swap",
});
```

- [ ] **Step 2: Atualizar a className do body**

Substituir:

```typescript
      <body className={`antialiased ${plusJakartaSans.variable} ${jost.variable}`} suppressHydrationWarning>
```

Por:

```typescript
      <body className={`antialiased ${inter.variable}`} suppressHydrationWarning>
```

- [ ] **Step 3: Rodar o build**

Run: `cd frontend && npm run build`
Expected: build sem erros — a variável `--font-sans` gerada pelo `next/font` é consumida por `--font-display`/`--font-body` no `globals.css` (Task 1, Step 1).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/layout.tsx
git commit -m "feat(design): trocar tipografia para Inter"
```

---

## Task 4: Novo logo (calendário com check)

**Files:**
- Create: `frontend/app/components/icons/CalendarCheckLogo.tsx`
- Create: `frontend/app/icon.svg`
- Delete: `frontend/app/favicon.ico`

- [ ] **Step 1: Criar o componente do logo**

```typescript
type CalendarCheckLogoProps = {
  size?: number;
  variant?: "badge" | "mark";
};

export default function CalendarCheckLogo({ size = 32, variant = "badge" }: CalendarCheckLogoProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 88 88" role="img" aria-label="Hagendei">
      {variant === "badge" ? (
        <rect x="4" y="4" width="80" height="80" rx="20" fill="#1e3a5f" />
      ) : null}
      <rect x="24" y="26" width="40" height="36" rx="6" fill="#ffffff" />
      <rect x="24" y="26" width="40" height="10" rx="6" fill="#d99b3f" />
      <circle cx="34" cy="20" r="3" fill="#ffffff" />
      <circle cx="54" cy="20" r="3" fill="#ffffff" />
      <path
        d="M32 46 L40 54 L56 40"
        stroke="#1e3a5f"
        strokeWidth="4"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
```

Uso: `variant="badge"` (padrão) quando o logo precisa se virar sozinho (favicon). `variant="mark"` quando já existe uma caixa colorida ao redor no CSS do componente pai (evita caixa dupla) — é o caso da Sidebar (Task 6) e do login (Task 9).

- [ ] **Step 2: Criar o favicon estático**

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 88 88">
  <rect x="4" y="4" width="80" height="80" rx="20" fill="#1e3a5f"/>
  <rect x="24" y="26" width="40" height="36" rx="6" fill="#ffffff"/>
  <rect x="24" y="26" width="40" height="10" rx="6" fill="#d99b3f"/>
  <circle cx="34" cy="20" r="3" fill="#ffffff"/>
  <circle cx="54" cy="20" r="3" fill="#ffffff"/>
  <path d="M32 46 L40 54 L56 40" stroke="#1e3a5f" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

Salvar em `frontend/app/icon.svg` — Next.js App Router reconhece esse nome de arquivo automaticamente como o ícone do site (convenção de metadata files), sem precisar registrar em `layout.tsx`.

- [ ] **Step 3: Remover o favicon antigo**

```bash
rm frontend/app/favicon.ico
```

(Ter os dois ao mesmo tempo pode causar ambiguidade sobre qual ícone o navegador usa.)

- [ ] **Step 4: Rodar o build e verificar visualmente**

Run: `cd frontend && npm run build && npm run start`
Then: abrir `http://localhost:3000/login` no navegador e conferir a aba — deve mostrar o novo ícone de calendário.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/components/icons/CalendarCheckLogo.tsx frontend/app/icon.svg
git rm frontend/app/favicon.ico
git commit -m "feat(design): novo logo (calendario com check) substitui favicon antigo"
```

---

## Task 5: Componente Sidebar (navegação lateral)

**Files:**
- Create: `frontend/app/components/Sidebar.tsx`
- Create: `frontend/app/components/Sidebar.module.css`

- [ ] **Step 1: Criar o componente**

```typescript
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import CalendarCheckLogo from "./icons/CalendarCheckLogo";
import styles from "./Sidebar.module.css";

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export type NavItem = {
  href: string;
  label: string;
  icon: React.ElementType;
};

type SidebarProps = {
  navItems: NavItem[];
};

export default function Sidebar({ navItems }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar} aria-label="Navegacao principal">
      <Link href="/" className={styles.brand} aria-label="Hagendei">
        <CalendarCheckLogo size={26} variant="mark" />
      </Link>

      <nav className={styles.nav}>
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cx(styles.navLink, isActive && styles.navLinkActive)}
            >
              <Icon size={20} />
              <span className={styles.tooltip}>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: Criar o CSS module**

```css
.sidebar {
  width: 64px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22px;
  padding: 16px 0;
  background: var(--accent);
}

.brand {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  text-decoration: none;
}

.nav {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.navLink {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  color: rgba(255, 255, 255, 0.62);
  text-decoration: none;
  transition: background 0.15s ease, color 0.15s ease;
}

.navLink:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
}

.navLinkActive {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.12);
}

.navLinkActive::before {
  content: "";
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 22px;
  border-radius: 2px;
  background: var(--warm);
}

.tooltip {
  position: absolute;
  left: calc(100% + 10px);
  top: 50%;
  transform: translateY(-50%);
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  background: var(--ink);
  color: #ffffff;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  z-index: 50;
}

.navLink:hover .tooltip {
  opacity: 1;
}

@media (max-width: 768px) {
  .sidebar {
    width: 56px;
  }
  .tooltip {
    display: none;
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/components/Sidebar.tsx frontend/app/components/Sidebar.module.css
git commit -m "feat(design): componente Sidebar (navegacao lateral com icones)"
```

(Ainda não é usado em lugar nenhum — a troca de fato acontece no Task 7. Nada quebra até lá.)

---

## Task 6: Componente TopBar

**Files:**
- Create: `frontend/app/components/TopBar.tsx`
- Create: `frontend/app/components/TopBar.module.css`

- [ ] **Step 1: Criar o componente**

```typescript
"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { logout } from "@/services/auth";
import ThemeToggle from "./ThemeToggle";
import { NotificacoesSino } from "./NotificacoesSino";
import { useNotificacoesContext } from "./NotificacoesProvider";
import styles from "./TopBar.module.css";

type TopBarProps = {
  tenantName: string;
  sectionLabel: string;
};

export default function TopBar({ tenantName, sectionLabel }: TopBarProps) {
  const router = useRouter();
  const notif = useNotificacoesContext();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className={styles.topBar}>
      <div className={styles.titles}>
        <span className={styles.tenantName}>{tenantName}</span>
        <span className={styles.sectionLabel}>{sectionLabel}</span>
      </div>

      <div className={styles.actions}>
        <ThemeToggle />

        <NotificacoesSino
          notificacoes={notif.notificacoes}
          naoLidas={notif.naoLidas}
          marcarLida={notif.marcarLida}
          marcarTodasLidas={notif.marcarTodasLidas}
          confirmarPresencaNotif={notif.confirmarPresencaNotif}
          marcarNovoAgendamentoLido={notif.marcarNovoAgendamentoLido}
        />

        <button type="button" className={styles.logoutButton} onClick={handleLogout}>
          <LogOut size={16} />
          <span>Sair</span>
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Criar o CSS module**

```css
.topBar {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 20px;
  background: var(--canvas);
  border-bottom: 1px solid var(--line);
}

.titles {
  display: grid;
  min-width: 0;
}

.tenantName {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ink);
}

.sectionLabel {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--warm);
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.logoutButton {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--ink-muted);
  font-family: var(--font-body);
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease;
}

.logoutButton:hover {
  transform: translateY(-1px);
  border-color: var(--ink-subtle);
  color: var(--ink);
}

@media (max-width: 640px) {
  .topBar {
    padding: 10px 14px;
  }
  .tenantName {
    font-size: 13px;
  }
  .logoutButton span {
    display: none;
  }
  .logoutButton {
    padding: 0 10px;
    min-width: 38px;
    justify-content: center;
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/components/TopBar.tsx frontend/app/components/TopBar.module.css
git commit -m "feat(design): componente TopBar (titulo da secao + acoes)"
```

---

## Task 7: Trocar Header por Sidebar+TopBar no AppShell

**Files:**
- Modify: `frontend/app/components/AppShell.tsx`
- Create: `frontend/app/components/AppShell.module.css`
- Delete: `frontend/app/components/Header.tsx`
- Delete: `frontend/app/components/Header.module.css`

- [ ] **Step 1: Criar o CSS do layout do shell**

```css
.shell {
  display: flex;
  min-height: 100dvh;
}

.mainColumn {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.content {
  flex: 1;
  min-width: 0;
}
```

- [ ] **Step 2: Reescrever o AppShell**

Substituir o conteúdo inteiro de `frontend/app/components/AppShell.tsx` por:

```typescript
"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import {
  BarChart2,
  CalendarDays,
  LayoutDashboard,
  Settings,
  Settings2,
  Shield,
} from "lucide-react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { useTenantTheme } from "@/hooks/useTenantTheme";
import { useAuthSession } from "@/services/auth";
import { NotificacoesProvider } from "./NotificacoesProvider";
import styles from "./AppShell.module.css";

type AppShellProps = {
  children: ReactNode;
};

const TOKEN_ACTION_PREFIXES = ["/confirmar/", "/cancelar/", "/reagendar/"];

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  useTenantTheme();
  const session = useAuthSession();

  const inLogin = pathname === "/login";
  const isPublicBookingById = pathname.startsWith("/agendar/");
  const isTokenActionPage = TOKEN_ACTION_PREFIXES.some((p) => pathname.startsWith(p));
  const ADMIN_PATHS = ["/login", "/admin", "/agenda", "/gestao", "/dashboard", "/configuracoes", "/upgrade", "/painel"];
  const isPublicBookingPath =
    !isPublicBookingById &&
    !isTokenActionPage &&
    /^\/[^/]+$/.test(pathname) &&
    !ADMIN_PATHS.includes(pathname);

  const hideNav = inLogin || isPublicBookingPath || isPublicBookingById || isTokenActionPage;

  const isAdmin = session?.tenantId === "admin";
  const inAdminPage = pathname.startsWith("/admin");
  const navItems = [
    { href: "/", label: "Painel", icon: LayoutDashboard },
    { href: "/agenda", label: "Agenda", icon: CalendarDays },
    { href: "/gestao", label: "Gestao", icon: Settings2 },
    ...(!isAdmin && session?.plan === "premium" ? [{ href: "/dashboard", label: "Dashboard", icon: BarChart2 }] : []),
    ...(!isAdmin ? [{ href: "/configuracoes", label: "Config.", icon: Settings }] : []),
    ...(isAdmin && !inAdminPage ? [{ href: "/admin", label: "Admin", icon: Shield }] : []),
  ];
  const activeItem = navItems.find((item) => item.href === pathname);
  const tenantName = session?.tenantName ?? "Estabelecimento";

  if (hideNav) {
    return children;
  }

  return (
    <NotificacoesProvider>
      <div className={styles.shell}>
        <Sidebar navItems={navItems} />
        <div className={styles.mainColumn}>
          <TopBar tenantName={tenantName} sectionLabel={activeItem?.label ?? tenantName} />
          <div className={styles.content}>{children}</div>
        </div>
      </div>
    </NotificacoesProvider>
  );
}
```

- [ ] **Step 3: Apagar o Header antigo**

```bash
rm frontend/app/components/Header.tsx frontend/app/components/Header.module.css
```

- [ ] **Step 4: Rodar o build**

Run: `cd frontend && npm run build`
Expected: build sem erros. Se aparecer erro de import não resolvido, é sinal de que algum outro arquivo ainda importa `./Header` — buscar com `grep -rn "components/Header" frontend/app` e resolver antes de prosseguir.

- [ ] **Step 5: Verificar visualmente no navegador**

Run: `cd frontend && npm run start`
Then: logar no sistema (`/login`) e navegar por Painel, Agenda, Gestão, Configurações — confirmar que a barra lateral aparece à esquerda, o item ativo tem o indicador âmbar, e o topo mostra nome do estabelecimento + seção atual + tema/notificações/sair funcionando.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/components/AppShell.tsx frontend/app/components/AppShell.module.css
git rm frontend/app/components/Header.tsx frontend/app/components/Header.module.css
git commit -m "feat(design): substituir menu no topo por barra lateral fixa"
```

---

## Task 8: Atualizar a tela de login

**Contexto:** `frontend/app/login/page.module.css` usa cores fixas (não variáveis) porque a tela não reage ao tema claro/escuro do app — é um design fixo. Por isso as cores são trocadas literalmente, não via `var()`.

**Files:**
- Modify: `frontend/app/login/page.tsx`
- Modify: `frontend/app/login/page.module.css`

- [ ] **Step 1: Trocar o ícone no page.tsx**

Substituir o import:

```typescript
import { Copy, Eye, Headset, Laptop, MessageCircle, ShieldCheck, User, X } from "lucide-react";
```

Por:

```typescript
import { Copy, Eye, Headset, MessageCircle, ShieldCheck, User, X } from "lucide-react";
import CalendarCheckLogo from "../components/icons/CalendarCheckLogo";
```

Substituir o uso do ícone (linha ~157):

```typescript
            {/* Laptop já é o ícone usado no login atual — mantido por consistência */}
            <Laptop size={18} color="white" />
```

Por:

```typescript
            <CalendarCheckLogo size={20} variant="mark" />
```

- [ ] **Step 2: Atualizar as cores em page.module.css**

Fazer as seguintes trocas exatas (uma de cada vez, cada uma é uma única ocorrência única pelo contexto do seletor):

1. Em `.left`: `background: #1a1a1a;` → `background: #14283f;`
2. Em `.right`: `background: #f9f9f7;` → `background: #f6f8fb;`
3. Em `.leftIcon`: `background: #d4930a;` → `background: #1e3a5f;`
4. Em `.leftDivider`: `background: #d4930a;` → `background: #d99b3f;`
5. Em `.avatar`: `border: 2px solid #1a1a1a;` → `border: 2px solid #14283f;`
6. Em `.formEyebrow`: `color: #d4930a;` → `color: #d99b3f;`
7. Em `.mfaIntro`: `color: #74520a;` → `color: #7a5726;`
8. Em `.recoveryGrid code`: `border: 1px solid #e0e0dc;` → `border: 1px solid #e5e9ee;`
9. No input principal (bloco com `min-height: 46px; padding: 0 40px 0 14px;`): `border: 1px solid #e0e0dc;` → `border: 1px solid #e5e9ee;`
10. Em `.input:focus`: `border-color: #d4930a;` → `border-color: #d99b3f;` e `box-shadow: 0 0 0 3px rgba(212,147,10,0.12);` → `box-shadow: 0 0 0 3px rgba(217,155,63,0.12);`
11. Em `.supportLink`: `color: #d4930a;` → `color: #d99b3f;`
12. Em `.supportLink:hover`: `color: #a36f06;` → `color: #a67a34;`

Não mexer em: `#1a1a1a` usado como cor de texto no painel direito (`.formTitle`, `.copyButton`, inputs, `.submit`, `.ghostButton:hover`) — esses continuam batendo com `--ink`, que não mudou. Não mexer no gradiente verde do WhatsApp (`#20b767, #13834a`) — é a cor oficial da marca WhatsApp, não do Hagendei.

- [ ] **Step 3: Rodar o build**

Run: `cd frontend && npm run build`
Expected: sem erros.

- [ ] **Step 4: Verificar visualmente**

Run: `cd frontend && npm run start`
Then: abrir `/login` no navegador — painel esquerdo deve estar azul-petróleo escuro (não mais preto), ícone/divisor/eyebrow em âmbar, painel direito em branco levemente azulado.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/login/page.tsx frontend/app/login/page.module.css
git commit -m "feat(design): aplicar nova paleta e logo na tela de login"
```

---

## Task 9: Destaque âmbar no indicador-chave + padrão de tema em Configurações

**Files:**
- Modify: `frontend/app/page.module.css`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/gestao/page.module.css`
- Modify: `frontend/app/gestao/page.tsx`
- Modify: `frontend/app/agenda/page.module.css`
- Modify: `frontend/app/agenda/page.tsx`
- Modify: `frontend/app/configuracoes/page.tsx`

- [ ] **Step 1: Adicionar a classe de destaque em `app/page.module.css`**

Adicionar logo após a regra `.statCard { ... }` (linha ~147):

```css
.statCardHighlight {
  border-left: 3px solid var(--warm);
}
```

- [ ] **Step 2: Aplicar no primeiro card em `app/page.tsx`**

Encontrar o componente local `StatCard` (linha ~22) e adicionar suporte a uma prop `highlight`:

```typescript
function StatCard({
  label,
  value,
  helper,
  icon,
  highlight,
}: {
  label: string;
  value: string;
  helper: string;
  icon: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <article className={cx(styles.statCard, highlight && styles.statCardHighlight)}>
      <div className={styles.statIcon}>{icon}</div>
      <div className={styles.statContent}>
        <span className={styles.statLabel}>{label}</span>
        <strong className={styles.statValue}>{value}</strong>
        <span className={styles.statHelper}>{helper}</span>
      </div>
    </article>
  );
}
```

Depois, no uso do primeiro `<StatCard>` (label="Agendamentos", linha ~162), adicionar a prop:

```typescript
          <StatCard
            label="Agendamentos"
            value={loading ? "..." : String(data.totalAgendamentos)}
            helper="Volume total da agenda"
            icon={<CalendarDays size={20} />}
            highlight
          />
```

- [ ] **Step 3: Adicionar a classe de destaque em `app/gestao/page.module.css`**

Adicionar logo após a regra `.statCard { ... }`:

```css
.statCardHighlight {
  border-left: 3px solid var(--warm);
}
```

- [ ] **Step 4: Aplicar no primeiro card em `app/gestao/page.tsx`**

Substituir o `StatCard` local (linha ~381):

```typescript
function StatCard({
  icon,
  label,
  value,
  helper,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  helper: string;
}) {
  return (
    <article className={styles.statCard}>
      <div className={styles.statIcon}>{icon}</div>
      <div className={styles.statContent}>
        <span className={styles.statLabel}>{label}</span>
        <strong className={styles.statValue}>{value}</strong>
        <span className={styles.statHelper}>{helper}</span>
      </div>
    </article>
  );
}
```

Por:

```typescript
function StatCard({
  icon,
  label,
  value,
  helper,
  highlight,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  helper: string;
  highlight?: boolean;
}) {
  return (
    <article className={cx(styles.statCard, highlight && styles.statCardHighlight)}>
      <div className={styles.statIcon}>{icon}</div>
      <div className={styles.statContent}>
        <span className={styles.statLabel}>{label}</span>
        <strong className={styles.statValue}>{value}</strong>
        <span className={styles.statHelper}>{helper}</span>
      </div>
    </article>
  );
}
```

(O helper `cx` já existe em `app/gestao/page.tsx` linha 103, não precisa criar.)

No uso do primeiro `<StatCard>` (label="Agendamentos", linha ~925), adicionar a prop:

```typescript
          <StatCard
            icon={<CalendarDays size={20} />}
            label="Agendamentos"
            value={String(agendamentos.length)}
            helper={proximoAgendamento ? "Com proximos horarios cadastrados" : "Nenhum horario futuro"}
            highlight
          />
```

- [ ] **Step 5: Adicionar a classe de destaque em `app/agenda/page.module.css`**

Adicionar logo após a regra `.statCard { ... }`:

```css
.statCardHighlight {
  border-left: 3px solid var(--warm);
}
```

- [ ] **Step 6: Aplicar no primeiro card em `app/agenda/page.tsx`**

Substituir o `StatCard` local (linha ~42):

```typescript
function StatCard({
  label,
  value,
  helper,
  icon,
}: {
  label: string;
  value: string;
  helper: string;
  icon: React.ReactNode;
}) {
  return (
    <article className={styles.statCard}>
      <div className={styles.statIcon}>{icon}</div>
      <div className={styles.statContent}>
        <span className={styles.statLabel}>{label}</span>
        <strong className={styles.statValue}>{value}</strong>
        <span className={styles.statHelper}>{helper}</span>
      </div>
    </article>
  );
}
```

Por:

```typescript
function StatCard({
  label,
  value,
  helper,
  icon,
  highlight,
}: {
  label: string;
  value: string;
  helper: string;
  icon: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <article className={cx(styles.statCard, highlight && styles.statCardHighlight)}>
      <div className={styles.statIcon}>{icon}</div>
      <div className={styles.statContent}>
        <span className={styles.statLabel}>{label}</span>
        <strong className={styles.statValue}>{value}</strong>
        <span className={styles.statHelper}>{helper}</span>
      </div>
    </article>
  );
}
```

(O helper `cx` já existe em `app/agenda/page.tsx` linha 38, não precisa criar.)

No uso do primeiro `<StatCard>` (label="Slots do dia", linha ~169), adicionar a prop:

```typescript
          <StatCard
            label="Slots do dia"
            value={loading ? "..." : String(totalSlots)}
            helper="Todos os horarios validos na agenda"
            icon={<CalendarDays size={20} />}
            highlight
          />
```

- [ ] **Step 7: Atualizar o preset de tema padrão em Configurações**

Em `frontend/app/configuracoes/page.tsx`, substituir:

```typescript
const PRESETS: Preset[] = [
  { label: "Indigo", accent: "#4f46e5", bg: "#ffffff" },
  { label: "Teal", accent: "#0d9488", bg: "#ffffff" },
  { label: "Rosa", accent: "#db2777", bg: "#ffffff" },
  { label: "Ambar", accent: "#d4930a", bg: "#ffffff" },
  { label: "Ardosia", accent: "#475569", bg: "#f8fafc" },
  { label: "Coral", accent: "#e2522b", bg: "#fffaf8" },
  { label: "Noturno", accent: "#e5a820", bg: "#0f0f0e" },
];
```

Por:

```typescript
const PRESETS: Preset[] = [
  { label: "Petroleo", accent: "#1e3a5f", bg: "#ffffff" },
  { label: "Teal", accent: "#0d9488", bg: "#ffffff" },
  { label: "Rosa", accent: "#db2777", bg: "#ffffff" },
  { label: "Ambar", accent: "#d99b3f", bg: "#ffffff" },
  { label: "Ardosia", accent: "#475569", bg: "#f8fafc" },
  { label: "Coral", accent: "#e2522b", bg: "#fffaf8" },
  { label: "Noturno", accent: "#e5a820", bg: "#0f0f0e" },
];
```

E substituir o fallback do estado:

```typescript
  const [accentColor, setAccentColor] = useState(session?.accentColor ?? "#4f46e5");
```

Por:

```typescript
  const [accentColor, setAccentColor] = useState(session?.accentColor ?? "#1e3a5f");
```

- [ ] **Step 8: Rodar o build**

Run: `cd frontend && npm run build`
Expected: sem erros.

- [ ] **Step 9: Verificar visualmente**

Run: `cd frontend && npm run start`
Then: em `/`, `/gestao` e `/agenda`, confirmar que o primeiro card de métrica tem uma borda âmbar à esquerda. Em `/configuracoes` (aba Tema), confirmar que a primeira opção de preset agora é "Petroleo" com a cor certa.

- [ ] **Step 10: Commit**

```bash
git add frontend/app/page.tsx frontend/app/page.module.css frontend/app/gestao/page.tsx frontend/app/gestao/page.module.css frontend/app/agenda/page.tsx frontend/app/agenda/page.module.css frontend/app/configuracoes/page.tsx
git commit -m "feat(design): destaque ambar no indicador-chave e novo preset padrao de tema"
```

---

## Task 10: Verificação visual final

**Files:** nenhum (apenas verificação — não deve gerar diffs de código; se gerar, é sinal de que algo passou batido nas tarefas anteriores)

- [ ] **Step 1: Build de produção completo**

Run: `cd frontend && npm run build`
Expected: build conclui sem erros ou warnings de tipo novos.

- [ ] **Step 2: Rodar `tsc` isoladamente**

Run: `cd frontend && npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 3: Passada visual manual — modo claro**

Run: `cd frontend && npm run start`
Then: no navegador, visitar cada uma destas rotas logado como tenant normal e como admin, conferindo paleta petróleo/âmbar, tipografia Inter, e a barra lateral funcionando (item ativo destacado, navegação funcional):
- `/login`
- `/` (Painel)
- `/agenda`
- `/gestao`
- `/dashboard` (conta premium)
- `/configuracoes`
- `/admin`, `/admin/master`, `/admin/seguranca` (conta admin)
- `/upgrade`

- [ ] **Step 4: Passada visual manual — modo escuro**

Usando o seletor de tema (ThemeToggle na TopBar), repetir a mesma passada em dark mode nas mesmas rotas (exceto `/login`, que não reage a tema).

- [ ] **Step 5: Conferir que nada externo quebrou**

Run: `cd backend && python -m pytest`
Expected: 349 passed (nenhuma mudança de backend neste plano — só confirma que o ambiente de teste ainda está saudável).

- [ ] **Step 6: Relatar resultado**

Se tudo passou: registrar no PR/commit final que a verificação visual foi feita manualmente (não existe suíte de regressão visual automatizada hoje). Se algo destoar da paleta em alguma tela, anotar a tela e o elemento específico como follow-up (não corrigir dentro desta task — task de verificação não deve introduzir código novo).
