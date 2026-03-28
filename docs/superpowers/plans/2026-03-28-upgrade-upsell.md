# Upgrade Upsell — Plano Básico Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ao clicar "Adicionar profissional" com o limite do plano básico atingido, exibir um modal de upsell e criar a página `/upgrade` com comparativo de planos.

**Architecture:** Interceptação do clique em `gestao/page.tsx` via nova state `showUpgradeModal`; modal inline usando o componente `<Modal>` existente; nova rota Next.js `/upgrade` com cards de plano e CSS tokens do design system.

**Tech Stack:** Next.js 14 (App Router), React, CSS Modules, Lucide React

---

## Arquivos

| Arquivo | Ação |
|---|---|
| `frontend/app/gestao/page.tsx` | Modificar — state + interceptação + modal de upsell |
| `frontend/app/upgrade/page.tsx` | Criar — página de comparativo de planos |
| `frontend/app/upgrade/page.module.css` | Criar — estilos da página de upgrade |

---

## Task 1: Interceptação do clique e modal de upsell em `gestao/page.tsx`

**Files:**
- Modify: `frontend/app/gestao/page.tsx`

### Passo a passo

- [ ] **Step 1: Adicionar state `showUpgradeModal`**

Localizar o bloco de states dos modais (~linha 413–416) e adicionar após `showBarbeiroModal`:

```tsx
const [showUpgradeModal, setShowUpgradeModal] = useState(false);
```

- [ ] **Step 2: Criar função `abrirModalOuUpgrade`**

Adicionar logo após a função `abrirModalBarbeiro` (linha ~659):

```tsx
function abrirModalOuUpgrade() {
  if (!isPremiumPlan && limiteBarbeirosAtingido) {
    setShowUpgradeModal(true);
  } else {
    abrirModalBarbeiro();
  }
}
```

- [ ] **Step 3: Trocar chamadas do botão "Adicionar profissional"**

Linha ~891 — trocar `onClick={() => abrirModalBarbeiro()}` por:

```tsx
onClick={abrirModalOuUpgrade}
```

O botão "Criar primeiro profissional" do empty state (~linha 925) **não muda** — quando não há profissionais o limite não foi atingido.

- [ ] **Step 4: Adicionar import do `useRouter` do Next.js**

No topo do arquivo, localizar a linha com `import { useAuthSession }` e verificar se `useRouter` já está importado. Se não estiver, adicionar:

```tsx
import { useRouter } from "next/navigation";
```

E dentro do componente `GestaoPage`, após `const authSession = useAuthSession();`:

```tsx
const router = useRouter();
```

- [ ] **Step 5: Adicionar o modal de upsell no JSX**

Localizar o bloco de modais no final do JSX (próximo à linha 1376, onde fica `<Modal isOpen={showBarbeiroModal}`). Adicionar **antes** desse bloco:

```tsx
<Modal
  isOpen={showUpgradeModal}
  onClose={() => setShowUpgradeModal(false)}
  title="Limite do plano básico atingido"
  size="sm"
>
  <div className={styles.upgradeModalBody}>
    <p className={styles.upgradeModalText}>
      O plano básico permite <strong>1 profissional</strong> ativo. Com o{" "}
      <strong>Premium</strong> você pode cadastrar até 3 profissionais e ter acesso
      a dashboard financeiro, análise de clientes e suporte prioritário.
    </p>
    <div className={styles.upgradeModalActions}>
      <ActionButton variant="primary" onClick={() => router.push("/upgrade")}>
        Fazer upgrade
      </ActionButton>
      <ActionButton variant="ghost" onClick={() => setShowUpgradeModal(false)}>
        Agora não
      </ActionButton>
    </div>
  </div>
</Modal>
```

- [ ] **Step 6: Adicionar estilos do modal de upsell em `gestao/page.module.css`**

Abrir `frontend/app/gestao/page.module.css` e adicionar ao final:

```css
/* ── Upgrade upsell modal ─────────────────────────────────── */
.upgradeModalBody {
  display: grid;
  gap: 24px;
}

.upgradeModalText {
  margin: 0;
  color: var(--ink-muted);
  line-height: 1.65;
}

.upgradeModalActions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
```

- [ ] **Step 7: Testar manualmente**

1. Fazer login com uma conta no plano básico
2. Cadastrar 1 profissional (se ainda não houver)
3. Clicar "Adicionar profissional"
4. Verificar que o modal de upsell abre (não o modal de cadastro)
5. Clicar "Agora não" — modal fecha
6. Clicar "Adicionar profissional" → "Fazer upgrade" → deve navegar para `/upgrade` (404 por enquanto, ok)

- [ ] **Step 8: Commit**

```bash
git add frontend/app/gestao/page.tsx frontend/app/gestao/page.module.css
git commit -m "feat: modal de upsell ao atingir limite de profissionais no plano básico"
```

---

## Task 2: Página `/upgrade`

**Files:**
- Create: `frontend/app/upgrade/page.tsx`
- Create: `frontend/app/upgrade/page.module.css`

### Passo a passo

- [ ] **Step 1: Criar `frontend/app/upgrade/page.module.css`**

```css
/* ── Shell ────────────────────────────────────────────────── */
.page {
  min-height: 100vh;
  background: var(--canvas);
  color: var(--ink);
}

.shell {
  max-width: 960px;
  margin: 0 auto;
  padding: 40px 20px 80px;
}

/* ── Voltar ───────────────────────────────────────────────── */
.backLink {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.875rem;
  color: var(--ink-muted);
  text-decoration: none;
  margin-bottom: 40px;
  transition: color 0.15s;
}

.backLink:hover {
  color: var(--ink);
}

/* ── Header ───────────────────────────────────────────────── */
.header {
  text-align: center;
  margin-bottom: 48px;
  display: grid;
  gap: 12px;
}

.eyebrow {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-dark);
  margin: 0;
}

.title {
  margin: 0;
  font-size: clamp(1.8rem, 3vw, 2.8rem);
  line-height: 1.05;
  letter-spacing: -0.03em;
}

.subtitle {
  margin: 0;
  color: var(--ink-muted);
  font-size: 1rem;
  line-height: 1.65;
}

/* ── Grid de planos ───────────────────────────────────────── */
.plansGrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

@media (max-width: 600px) {
  .plansGrid {
    grid-template-columns: 1fr;
  }
}

/* ── Card de plano ────────────────────────────────────────── */
.planCard {
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  background: var(--surface);
  padding: 32px 28px;
  display: grid;
  gap: 24px;
  position: relative;
}

.planCardHighlight {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft), var(--shadow-md);
}

/* ── Cabeçalho do card ────────────────────────────────────── */
.planCardHeader {
  display: grid;
  gap: 8px;
}

.planBadgeRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.planName {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.planBadge {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: var(--accent);
  color: #fff;
  border-radius: 999px;
  padding: 3px 10px;
}

.planPrice {
  margin: 0;
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
}

.planPriceSub {
  font-size: 0.875rem;
  font-weight: 400;
  color: var(--ink-muted);
  margin-left: 4px;
}

.planDescription {
  margin: 0;
  color: var(--ink-muted);
  font-size: 0.9rem;
  line-height: 1.55;
}

/* ── Features ─────────────────────────────────────────────── */
.featureList {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}

.featureItem {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.9rem;
  color: var(--ink);
}

.featureIcon {
  flex-shrink: 0;
  margin-top: 1px;
}

.featureIconCheck {
  color: var(--accent);
}

.featureIconMissing {
  color: var(--ink-muted);
}

/* ── CTA ──────────────────────────────────────────────────── */
.ctaButton {
  width: 100%;
  padding: 12px 20px;
  border-radius: var(--radius-lg);
  border: none;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.ctaButtonPrimary {
  background: var(--accent);
  color: #fff;
}

.ctaButtonPrimary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ctaButtonSecondary {
  background: var(--surface-raised, var(--surface));
  color: var(--ink-muted);
  border: 1px solid var(--line);
  cursor: not-allowed;
}
```

- [ ] **Step 2: Criar `frontend/app/upgrade/page.tsx`**

```tsx
"use client";

import Link from "next/link";
import { ArrowLeft, Check, Minus } from "lucide-react";
import styles from "./page.module.css";

type Feature = {
  label: string;
  basico: boolean;
  premium: boolean;
};

const FEATURES: Feature[] = [
  { label: "Profissionais ativos", basico: false, premium: false }, // tratado à parte (texto customizado)
  { label: "Agendamentos ilimitados", basico: true, premium: true },
  { label: "Dashboard financeiro", basico: false, premium: true },
  { label: "Análise de clientes", basico: false, premium: true },
  { label: "Ranking de serviços", basico: false, premium: true },
  { label: "Suporte prioritário", basico: false, premium: true },
];

function FeatureIcon({ has }: { has: boolean }) {
  if (has) {
    return <Check size={16} className={`${styles.featureIcon} ${styles.featureIconCheck}`} />;
  }
  return <Minus size={16} className={`${styles.featureIcon} ${styles.featureIconMissing}`} />;
}

export default function UpgradePage() {
  return (
    <div className={styles.page}>
      <div className={styles.shell}>
        <Link href="/gestao" className={styles.backLink}>
          <ArrowLeft size={14} />
          Voltar para gestão
        </Link>

        <div className={styles.header}>
          <p className={styles.eyebrow}>Planos</p>
          <h1 className={styles.title}>Escolha seu plano</h1>
          <p className={styles.subtitle}>
            Comece grátis e faça upgrade quando precisar de mais recursos.
          </p>
        </div>

        <div className={styles.plansGrid}>
          {/* Plano Básico */}
          <div className={styles.planCard}>
            <div className={styles.planCardHeader}>
              <div className={styles.planBadgeRow}>
                <h2 className={styles.planName}>Básico</h2>
              </div>
              <p className={styles.planPrice}>
                Grátis
              </p>
              <p className={styles.planDescription}>
                Para quem está começando e precisa do essencial.
              </p>
            </div>

            <ul className={styles.featureList}>
              <li className={styles.featureItem}>
                <FeatureIcon has={true} />
                1 profissional ativo
              </li>
              {FEATURES.slice(1).map((f) => (
                <li key={f.label} className={styles.featureItem}>
                  <FeatureIcon has={f.basico} />
                  {f.label}
                </li>
              ))}
            </ul>

            <button disabled className={styles.ctaButton + " " + styles.ctaButtonSecondary}>
              Plano atual
            </button>
          </div>

          {/* Plano Premium */}
          <div className={`${styles.planCard} ${styles.planCardHighlight}`}>
            <div className={styles.planCardHeader}>
              <div className={styles.planBadgeRow}>
                <h2 className={styles.planName}>Premium</h2>
                <span className={styles.planBadge}>Recomendado</span>
              </div>
              <p className={styles.planPrice}>
                R$ 49<span className={styles.planPriceSub}>/mês</span>
              </p>
              <p className={styles.planDescription}>
                Para estabelecimentos que querem crescer com dados e mais equipe.
              </p>
            </div>

            <ul className={styles.featureList}>
              <li className={styles.featureItem}>
                <FeatureIcon has={true} />
                Até 3 profissionais ativos
              </li>
              {FEATURES.slice(1).map((f) => (
                <li key={f.label} className={styles.featureItem}>
                  <FeatureIcon has={f.premium} />
                  {f.label}
                </li>
              ))}
            </ul>

            <button disabled className={styles.ctaButton + " " + styles.ctaButtonPrimary}>
              Em breve
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Testar manualmente**

1. Navegar para `/upgrade` (ou clicar "Fazer upgrade" no modal da task 1)
2. Verificar que os dois cards aparecem lado a lado no desktop
3. Redimensionar para mobile (< 600px) — cards devem empilhar
4. Verificar que o card Premium tem borda accent e badge "Recomendado"
5. Verificar que ambos os botões estão desabilitados
6. Clicar "Voltar para gestão" — deve navegar para `/gestao`

- [ ] **Step 4: Commit**

```bash
git add frontend/app/upgrade/page.tsx frontend/app/upgrade/page.module.css
git commit -m "feat: página de comparativo de planos /upgrade"
```
