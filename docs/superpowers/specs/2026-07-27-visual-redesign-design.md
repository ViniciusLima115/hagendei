# Redesign visual do Hagendei

**Data:** 2026-07-27
**Status:** Aprovado para planejamento

## Contexto

O sistema foi rebrandeado de "Barbershop" para "Hagendei" e passou a se posicionar como uma plataforma de agendamento genérica (não mais exclusiva para barbearias). O visual atual (paleta indigo/roxa, Plus Jakarta Sans + Jost, menu horizontal no topo) foi considerado datado e genérico pelo usuário, e não reflete essa mudança de posicionamento.

Esta spec cobre um redesign visual completo do frontend (`frontend/`), sem alterar nenhuma lógica de negócio, rota de API, ou fluxo de dados — é puramente uma mudança de apresentação.

## Objetivo

Um visual que transmita **"profissional e confiável" + "caloroso e acessível"** ao mesmo tempo — sério o suficiente pra um dono de negócio confiar a operação do agendamento, mas próximo o suficiente pra não intimidar quem não é técnico.

## Sistema de design

### Paleta de cores

Substituir a paleta indigo atual por azul petróleo (autoridade/confiança) + âmbar (calor/destaque), mantendo fundo neutro claro.

**Light mode** (variáveis em `frontend/app/globals.css`):
```css
--ink:          #1a1a1a;   /* mantido */
--ink-muted:    #4a4a4a;   /* mantido */
--ink-subtle:   #9a9a9a;   /* mantido */
--canvas:       #f6f8fb;   /* era #f9f9f7 — leve ajuste pro tom frio-neutro do mockup C */
--surface:      #ffffff;   /* mantido */
--surface-alt:  #f0f2f5;   /* era #f0f0ee */
--line:         #e5e9ee;   /* era #e0e0dc */
--overlay:      rgba(0,0,0,0.48); /* mantido */

--accent:       #1e3a5f;   /* era #4f46e5 (indigo) — agora azul petróleo */
--accent-dark:  #142a44;   /* era #3730a3 */
--accent-soft:  #eaf0f5;   /* era #eef2ff */

--warm:         #d99b3f;   /* NOVO — âmbar, acento de calor (ativo na sidebar, borda de destaque em cards-chave, logo) */
--warm-soft:    #fdf3e2;   /* NOVO */

--success:      #166534;   /* mantido */
--success-soft: #f0fdf4;
--success-line: #bbf7d0;
--warning:      #854d0e;   /* mantido */
--warning-soft: #fefce8;
--warning-line: #fde68a;
--danger:       #991b1b;   /* mantido */
--danger-soft:  #fef2f2;
--danger-line:  #fecaca;
```

**Dark mode:**
```css
--accent:       #5b84ad;   /* petróleo clareado pra contraste em fundo escuro */
--accent-dark:  #4d7aa8;
--accent-soft:  rgba(30,58,95,0.35);

--warm:         #e0ac5f;   /* âmbar levemente dessaturado */
--warm-soft:    rgba(217,155,63,0.18);
```

`--radius-*` e `--shadow-*` são mantidos como estão (já adequados: 6-16px, sombras suaves).

### Tipografia

Trocar Plus Jakarta Sans (títulos) + Jost (corpo) por uma única família geométrica neutra: **Inter**, usada em títulos e corpo (pesos diferentes: 600-800 em títulos, 400-500 em corpo). Prioriza legibilidade em telas densas (tabela de agenda, listas de clientes/serviços).

Em `frontend/app/layout.tsx`: substituir os imports `Plus_Jakarta_Sans` e `Jost` de `next/font/google` por um único import de `Inter` (mesma técnica de self-hosting via `next/font`, sem CDN externo — evita requisições de terceiros). Em `globals.css`: `--font-display` e `--font-body` passam a apontar para a mesma variável Inter.

### Componentes

- Cantos arredondados moderados (mantém `--radius-md`/`--radius-lg` = 8-12px como padrão de cards e inputs)
- Sombras suaves mantidas (`--shadow-sm`/`--shadow-md`)
- Cards de métrica-chave (ex: faturamento do dia, no `StatCard`) ganham borda esquerda de 3px em `--warm` para destaque visual sem depender só de cor de fundo

## Navegação e layout

Substituir o menu horizontal fixo (`Header.tsx`) por uma **barra lateral fixa** (largura ~64px, só ícones, conforme mockup aprovado), em `--accent` (petróleo), com o item ativo destacado com um indicador em `--warm`. Labels dos itens aparecem via tooltip ao passar o mouse; o nome da seção atual (ex: "Painel", "Agenda") aparece como um pequeno cabeçalho no topo da área de conteúdo.

- Ícones dos itens de navegação mantidos (lucide-react: `LayoutDashboard`, `CalendarDays`, `Settings2`, `BarChart2`, `Settings`, `Shield`), só a estrutura de apresentação muda de horizontal pra vertical
- **Mobile/telas estreitas:** a sidebar colapsa para um drawer acionado por botão hambúrguer (padrão comum de app shell responsivo) — os itens de navegação continuam os mesmos, só muda a apresentação
- `AppShell.tsx` precisa da mesma lógica de "quando esconder a navegação" que já existe hoje (login, página pública de agendamento, páginas de ação por token), só trocando de "esconder Header" para "esconder Sidebar" e ajustando o layout de coluna vertical (topo) para linha horizontal (sidebar + conteúdo)

## Logo/ícone

Novo ícone: **calendário com check** — retângulo arredondado em `--accent`, "página" de calendário branca com topo em `--warm` e duas argolas, check em `--accent` dentro. Substitui o ícone atual (quadrado com monitor) em:
- Favicon (`frontend/public/`)
- Sidebar (topo)
- Tela de login

Formato: SVG inline (componente React), permitindo reutilizar cores via CSS variables (funciona em light/dark sem precisar de dois arquivos).

## Escopo — telas afetadas

Todas as telas do sistema, reutilizando os componentes compartilhados de `frontend/app/components/` (mudança nos componentes base propaga pra tudo):

| Tela | Rota |
|---|---|
| Login | `/login` |
| Painel | `/` |
| Agenda | `/agenda` |
| Gestão | `/gestao` |
| Dashboard (premium) | `/dashboard` |
| Configurações | `/configuracoes` |
| Admin (master + segurança) | `/admin`, `/admin/master`, `/admin/seguranca` |
| Upgrade | `/upgrade` |
| Página pública de agendamento | `/agendar/[estabelecimentoId]`, `/[slug]` |
| Páginas de ação por token | `/confirmar/[token]`, `/cancelar/[token]`, `/reagendar/[token]` |

Componentes base a re-estilizar: `Header.tsx` (→ nova `Sidebar.tsx`), `Card.tsx`, `Button.tsx`, `Badge.tsx`, `StatCard.tsx`, `Alert.tsx`, `Modal.tsx`, `FormInput.tsx`, `AgendaGrid.tsx`/`AgendaCell.tsx`, `ThemeToggle.tsx`, `NotificacoesSino.tsx`, `ToastNotificacao.tsx`.

## Fora de escopo

- Nenhuma mudança de lógica de negócio, rota de API, ou estrutura de dados
- Nenhuma nova funcionalidade
- Textos/copy das telas permanecem os mesmos (só estilo visual)
- O valor de negócio `Estabelecimento.tipo_servico = "barbearia"` não é afetado (não é uma questão de nomenclatura de marca)

## Verificação

- `npm run build` / `tsc` sem erros no frontend após a migração de tokens e componentes
- Passada visual manual (navegador) em cada tela listada acima, em light e dark mode, comparando antes/depois
- Suíte de testes do backend (349 passing) não é afetada — nenhuma mudança de lógica de negócio
- Nenhum teste de frontend automatizado de regressão visual existe hoje; a verificação é manual via navegador
