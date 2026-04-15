# Redesign Frontend — Visual Generalista e Moderno

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernizar a identidade visual do frontend, removendo completamente a estética de barbearia e adotando uma linguagem SaaS limpa e generalista que funcione para qualquer tipo de estabelecimento.

**Architecture:** As mudanças são todas de apresentação — tokens CSS, fontes, ícone de marca e cores padrão. Nenhuma lógica de negócio é alterada. O sistema de vocab (`lib/vocab.ts`) já lida com terminologia; este plano cuida do visual.

**Tech Stack:** Next.js 16 (App Router), CSS Modules, CSS Custom Properties, Google Fonts, lucide-react

---

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `frontend/app/layout.tsx` | Troca fonte `Libre_Baskerville` → `Plus_Jakarta_Sans`; atualiza metadata title |
| `frontend/app/globals.css` | Nova paleta (accent indigo), nova tipografia, badges em pill, input focus ring |
| `frontend/app/components/Header.tsx` | Ícone `Scissors` → `LayoutGrid`; eyebrow "Sistema interno" → "Gestão" |
| `frontend/app/components/Header.module.css` | `brandIcon` background usa `var(--accent)` em vez de hardcoded `#1a1a1a` |
| `frontend/app/components/ThemeToggle.tsx` | Remove o `<span className={styles.status}>` (texto "Dark"/"Light") |
| `frontend/app/configuracoes/page.tsx` | Default accent `#d4930a` → `#4f46e5`; reordena presets com Índigo primeiro |

---

### Task 1: Tipografia — substituir Libre Baskerville por Plus Jakarta Sans

**Files:**
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/globals.css`

`Libre Baskerville` é uma fonte serif clássica com forte associação a artesanato/barbearia. `Plus Jakarta Sans` é geométrica, moderna, amplamente usada em SaaS (Linear, Loom, etc.).

- [ ] **Step 1: Atualizar o import de fonte em layout.tsx**

```tsx
// frontend/app/layout.tsx
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

export const metadata: Metadata = {
  title: "Painel de Gestão",
  description: "Plataforma de gestão de agendamentos para estabelecimentos",
};

const themeScript = `
  (function () {
    try {
      var savedTheme = localStorage.getItem("virtualbarber:theme") || "system";
      var systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      var resolvedTheme = savedTheme === "system" ? systemTheme : savedTheme;
      document.documentElement.dataset.theme = resolvedTheme;
      document.documentElement.style.colorScheme = resolvedTheme;
    } catch (error) {
      document.documentElement.dataset.theme = "light";
      document.documentElement.style.colorScheme = "light";
    }
    try {
      var raw = localStorage.getItem("barbershop_auth_session");
      if (raw) {
        var s = JSON.parse(raw);
        if (s.accentColor) document.documentElement.style.setProperty("--accent", s.accentColor);
        if (s.accentColor) document.documentElement.style.setProperty("--accent-tenant", s.accentColor);
        if (s.bgColor) document.documentElement.style.setProperty("--bg-tenant", s.bgColor);
      }
    } catch (e) {}
  })();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className={`antialiased ${plusJakartaSans.variable} ${jost.variable}`} suppressHydrationWarning>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Atualizar variável tipográfica e estilo dos headings em globals.css**

Substituir apenas o bloco de tipografia inicial (linhas 1–7 e o bloco de headings):

```css
/* ─── TIPOGRAFIA ─────────────────────────────────────────── */
:root {
  --font-display: "Plus Jakarta Sans", system-ui, sans-serif;
  --font-body: "Jost", system-ui, sans-serif;
}
```

E o bloco de headings (antes: `letter-spacing: -0.03em`):

```css
/* ─── TIPOGRAFIA — HEADINGS ──────────────────────────────── */
h1, h2, h3, h4 {
  font-family: var(--font-display);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

h1 { font-size: clamp(1.75rem, 3.5vw, 3rem); }
h2 { font-size: clamp(1.35rem, 2.5vw, 2rem); }
h3 { font-size: 1.2rem; }
h4 { font-size: 1rem; }
```

- [ ] **Step 3: Verificar visualmente**

```bash
cd frontend && npm run dev
```

Abrir `http://localhost:3000`. Confirmar: títulos de página usam Plus Jakarta Sans (sem serifa); corpo do texto usa Jost. O header deve mostrar o nome do tenant sem serifa.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/globals.css
git commit -m "design: substituir Libre Baskerville por Plus Jakarta Sans nos headings"
```

---

### Task 2: Cor de destaque — trocar âmbar por índigo

**Files:**
- Modify: `frontend/app/globals.css`

Âmbar/dourado (`#d4930a`) remete fortemente a barbearia premium. Índigo (`#4f46e5`) é a cor SaaS mais neutra e moderna (Linear, Notion, Vercel usam variantes).

- [ ] **Step 1: Atualizar tokens de accent no light mode**

No bloco `/* ─── PALETA LIGHT MODE ─────── */`, substituir as três linhas de accent:

```css
  --accent:       #4f46e5;
  --accent-dark:  #3730a3;
  --accent-soft:  #eef2ff;
```

- [ ] **Step 2: Atualizar tokens de accent no dark mode**

No bloco `[data-theme="dark"]`, substituir:

```css
  --accent:       #818cf8;
  --accent-dark:  #6366f1;
  --accent-soft:  rgba(79,70,229,0.20);
```

- [ ] **Step 3: Corrigir focus ring do input (cor hardcoded)**

O `.input:focus` tem `box-shadow` com a cor âmbar hardcoded. Substituir:

```css
.input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(79,70,229,0.14);
}
```

- [ ] **Step 4: Verificar visualmente**

```bash
cd frontend && npm run dev
```

Confirmar: botões `.btn-accent`, links ativos, focus de inputs, eyebrows (`.eyebrow-section`) estão em índigo. Verificar dark mode (Cmd+Shift+D ou toggle).

- [ ] **Step 5: Commit**

```bash
git add frontend/app/globals.css
git commit -m "design: trocar accent âmbar por índigo — paleta SaaS generalista"
```

---

### Task 3: Ícone de marca e eyebrow do Header

**Files:**
- Modify: `frontend/app/components/Header.tsx`
- Modify: `frontend/app/components/Header.module.css`

`Scissors` é o símbolo definitivo de barbearia. `LayoutGrid` é neutro e adequado para qualquer tipo de gestão. O eyebrow "Sistema interno" soa técnico; "Gestão" é mais direto.

- [ ] **Step 1: Trocar ícone e eyebrow em Header.tsx**

```tsx
"use client";

import Link from "next/link";
import {
  BarChart2,
  CalendarDays,
  LayoutDashboard,
  LayoutGrid,
  Settings,
  Settings2,
  Shield,
  LogOut,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { logout, useAuthSession } from "@/services/auth";
import styles from "./Header.module.css";
import ThemeToggle from "./ThemeToggle";

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const session = useAuthSession();
  const tenantName = session?.tenantName ?? "Estabelecimento";
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

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className={styles.header}>
      <div className={cx("app-container", styles.shell)}>
        <Link href="/" className={styles.brand}>
          <div className={styles.brandIcon}>
            <LayoutGrid size={18} />
          </div>
          <div className={styles.brandCopy}>
            <span className={styles.brandEyebrow}>Gestão</span>
            <span className={styles.brandTitle}>{tenantName}</span>
          </div>
        </Link>

        <div className={styles.actions}>
          {!inAdminPage ? (
            <nav className={styles.nav} aria-label="Navegacao principal">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cx(styles.navLink, isActive && styles.navLinkActive)}
                  >
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          ) : null}

          <ThemeToggle />

          <button type="button" className={styles.logoutButton} onClick={handleLogout}>
            <LogOut size={16} />
            <span>Sair</span>
          </button>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Atualizar brandIcon para usar var(--accent) no background**

No `Header.module.css`, substituir a linha de background do `.brandIcon`:

```css
.brandIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  background: var(--accent);
  color: #ffffff;
}
```

- [ ] **Step 3: Verificar visualmente**

Abrir `http://localhost:3000`. Confirmar: ícone de grade (LayoutGrid) aparece na marca; o eyebrow diz "Gestão"; o fundo do ícone é índigo.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/components/Header.tsx frontend/app/components/Header.module.css
git commit -m "design: trocar Scissors por LayoutGrid e atualizar eyebrow do header"
```

---

### Task 4: Badges em pill shape

**Files:**
- Modify: `frontend/app/globals.css`

Badges quadradas (radius 6px) parecem antigas. Pill badges (radius 999px) são o padrão SaaS moderno.

- [ ] **Step 1: Atualizar `.badge` em globals.css**

Substituir a regra `.badge`:

```css
/* ─── BADGES ─────────────────────────────────────────────── */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  border: 1px solid;
}
```

- [ ] **Step 2: Verificar visualmente**

Na página de Agenda ou Gestão, confirmar que badges de status (Confirmado, Pendente, Cancelado) aparecem arredondados (pill shape).

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "design: badges em pill shape (border-radius 999px)"
```

---

### Task 5: Remover texto de status do ThemeToggle

**Files:**
- Modify: `frontend/app/components/ThemeToggle.tsx`

O span `.status` que exibe "Dark" / "Light" ao lado dos botões de tema é visual noise desnecessário e não é padrão SaaS.

- [ ] **Step 1: Remover o span de status em ThemeToggle.tsx**

```tsx
"use client";

import { MonitorCog, MoonStar, SunMedium } from "lucide-react";
import { ThemeMode, useTheme } from "./ThemeProvider";

import styles from "./ThemeToggle.module.css";

type ThemeToggleProps = {
  floating?: boolean;
};

const labels: Record<ThemeMode, string> = {
  light: "Claro",
  dark: "Escuro",
  system: "Sistema",
};

const options: ThemeMode[] = ["light", "dark", "system"];

export default function ThemeToggle({ floating = false }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();

  return (
    <div className={`${styles.group} ${floating ? styles.floating : ""}`}>
      {options.map((option) => {
        const active = theme === option;
        const icon =
          option === "light" ? (
            <SunMedium size={16} />
          ) : option === "dark" ? (
            <MoonStar size={16} />
          ) : (
            <MonitorCog size={16} />
          );

        return (
          <button
            key={option}
            type="button"
            className={`${styles.button} ${active ? styles.buttonActive : ""}`}
            onClick={() => setTheme(option)}
            aria-pressed={active}
            title={`Tema ${labels[option]}`}
          >
            {icon}
            <span>{labels[option]}</span>
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Remover `.status` do ThemeToggle.module.css**

```css
.group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--surface-alt);
}

.floating {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 60;
}

.button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 10px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--ink-subtle);
  font-family: var(--font-body);
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.button:hover {
  color: var(--ink);
  background: var(--surface);
}

.buttonActive {
  background: var(--surface);
  color: var(--ink);
  box-shadow: var(--shadow-sm);
}

@media (max-width: 640px) {
  .group {
    gap: 2px;
  }
  .button span {
    display: none;
  }
  .button {
    width: 36px;
    padding: 0;
    justify-content: center;
  }
}
```

- [ ] **Step 3: Verificar**

Confirmar que o ThemeToggle não exibe mais "Dark" ou "Light" ao lado dos botões. Verificar que o floating toggle nas páginas públicas ainda aparece corretamente.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/components/ThemeToggle.tsx frontend/app/components/ThemeToggle.module.css
git commit -m "design: remover texto de status redundante do ThemeToggle"
```

---

### Task 6: Preset de cores padrão → Índigo primeiro

**Files:**
- Modify: `frontend/app/configuracoes/page.tsx`

O default atual é `#d4930a` (âmbar). Com o redesign, o padrão do sistema passa a ser índigo. O preset "Índigo" deve vir primeiro na lista.

- [ ] **Step 1: Reordenar PRESETS e atualizar defaults**

Localizar a constante `PRESETS` (~linha 26) e os defaults de state (~linha 76–77). Substituir:

```tsx
const PRESETS: Preset[] = [
  { label: "Índigo",   accent: "#4f46e5", bg: "#ffffff" },
  { label: "Teal",     accent: "#0d9488", bg: "#ffffff" },
  { label: "Rosa",     accent: "#db2777", bg: "#ffffff" },
  { label: "Âmbar",   accent: "#d4930a", bg: "#ffffff" },
  { label: "Ardósia",  accent: "#475569", bg: "#f8fafc" },
  { label: "Coral",    accent: "#e2522b", bg: "#fffaf8" },
  { label: "Noturno",  accent: "#e5a820", bg: "#0f0f0e" },
];
```

E atualizar os defaults de state:

```tsx
const [accentColor, setAccentColor] = useState(session?.accentColor ?? "#4f46e5");
const [bgColor, setBgColor]         = useState(session?.bgColor     ?? "#ffffff");
```

- [ ] **Step 2: Verificar**

Abrir `/configuracoes` autenticado. Confirmar: "Índigo" aparece primeiro na grade de presets; ao abrir a página pela primeira vez sem tema salvo, a cor de preview mostra índigo.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/configuracoes/page.tsx
git commit -m "design: tornar Índigo o preset padrão de cor de destaque"
```

---

## Checklist final de verificação

Após todas as tasks:

- [ ] Nenhuma fonte com serifa visível em heading ou UI
- [ ] Accent color é índigo em toda a UI (botões, links ativos, foco de input, eyebrows, badges)
- [ ] Ícone no header é `LayoutGrid`, não `Scissors`
- [ ] Eyebrow do header diz "Gestão"
- [ ] Ícone do header tem fundo índigo (via `var(--accent)`)
- [ ] Badges são pill-shaped em todas as páginas
- [ ] ThemeToggle não exibe texto "Dark"/"Light"
- [ ] Preset "Índigo" é o primeiro na lista de Configurações
- [ ] Dark mode funciona corretamente em todos os itens acima
- [ ] Nenhum erro no console (TypeScript, CSS, hydration)

---

## Notas de arquitetura

- **Não alterar `lib/vocab.ts`**: o sistema de terminologia já é generalista por design.
- **Não alterar `localStorage` keys**: `virtualbarber:theme` e `barbershop_auth_session` são chaves internas invisíveis ao usuário.
- **Não alterar lógica de negócio**: nenhum serviço, hook de dados ou endpoint é tocado.
- **Tenant customization persiste**: tenants que já salvaram uma cor no backend continuarão vendo sua cor (o `themeScript` em `layout.tsx` aplica a cor salva antes do render).
