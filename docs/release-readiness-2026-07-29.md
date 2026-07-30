# Parecer de lançamento — 29/07/2026

## Resultado

**GO técnico condicionado aos gates externos de produção.**

O código, o schema novo, a adoção do banco legado validado, os fluxos de API,
o frontend e o pipeline automatizado passaram. O lançamento público só deve
ser autorizado depois dos itens manuais da seção final.

## Evidências executadas

| Área | Resultado |
|---|---|
| Backend completo | 363 testes aprovados |
| Cobertura backend | 82,25% (gate: 78%) |
| Fluxo PostgreSQL transacional | 28 verificações, rollback confirmado |
| Conta inativa/expirada | bloqueada em 9 superfícies públicas |
| Quota do plano grátis | painel e reserva pública bloqueiam após 30 no mês |
| Banco novo | `0001 -> 0005`, `alembic check` limpo |
| Clone integral do banco legado | baseline `0002 -> 0005`, check limpo |
| Preservação do clone | contagens e colunas comuns preservadas em 18 tabelas |
| Browser real | 9/9 smokes no Chrome headless |
| Playwright reproduzível | 5/5 fluxos críticos |
| Frontend | lint, TypeScript e build Next.js aprovados |
| Dependências de produção | npm audit: 0; pip-audit: 0 |
| Análise estática Python | Bandit: 0 achados médios/altos |
| Pipeline | deploy agora exige o mesmo SHA com CI verde |

Os fluxos de navegador cobrem guardas de rota, login, identidade visual,
reserva pública, telefone inválido, erro 422 legível, retorno de pagamento,
logout e reagendamento com troca efetiva de profissional e serviço.

## Correções relevantes resultantes dos testes

- atualização de usuário/senha sem o erro 422;
- tema e logo aplicados ao painel, login e agendamento público;
- plano `gratis` preservado corretamente no frontend;
- configurações carregam e salvam os dados atuais do estabelecimento;
- reservas públicas não contornam a quota mensal;
- contas inativas ou expiradas deixam de aceitar/expor operações públicas;
- reagendamento envia e aplica profissional e serviço selecionados;
- slots pendentes deixam de aparecer livres;
- lembretes WhatsApp entram no scheduler e têm retry com backoff;
- migration `0005` reconcilia banco novo e legado sem perder o payload histórico
  de webhook;
- CI ganhou PostgreSQL real, auditorias, build e Playwright;
- deploy automático deixa de publicar commits cujo CI falhou.

## Gates obrigatórios antes de produção

1. Confirmar a rotação dos segredos históricos: banco, JWT, administrador,
   Mercado Pago, Meta/WhatsApp, MegaAPI, e-mail e chave SSH.
2. Criar snapshot/branch do Neon e `pg_dump` criptografado; restaurar em outra
   base e comprovar a recuperação, incluindo as chaves de criptografia.
3. Na cópia restaurada, seguir o baseline documentado e repetir
   `alembic upgrade head` e `alembic check` antes de tocar no banco original.
4. Executar o workflow **Security and Tests** no SHA final e exigir resultado
   verde antes do deploy.
5. Configurar e conferir `APP_ENV`, URLs HTTPS, `EMAIL_ACTION_BASE_URL`,
   `TRUSTED_PROXY_IPS`, CORS, hosts e todos os segredos na VPS.
6. Validar com credenciais reais/sandbox as integrações Mercado Pago,
   WhatsApp/MegaAPI e SMTP; os testes locais não enviaram mensagens nem criaram
   transações externas reais.
7. Após o deploy, validar TLS, login, reserva, pagamento, webhooks, scheduler e
   backlog de lembretes conforme
   [`deploy-hagendei-checklist.md`](deploy-hagendei-checklist.md).

## Avisos não bloqueantes

- Next.js avisa que a convenção `middleware.ts` será substituída por `proxy`;
  a funcionalidade atual passou.
- A árvore de desenvolvimento do ESLint ainda recebe o advisory recente de
  `brace-expansion/minimatch`. A versão corrigida quebra os plugins atuais.
  Dependências carregadas em produção têm zero vulnerabilidades, e lint/build
  permanecem obrigatórios no CI.
- As migrations estruturais usam locks breves e não têm downgrade automático;
  a reversão operacional é pelo backup restaurável e validado.

