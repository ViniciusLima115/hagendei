# Auditoria de Seguranca - Hagendei

Data da auditoria: 2026-07-14
Escopo: repositorio completo do Hagendei, incluindo frontend, backend, banco/ORM, autenticacao, multiestabelecimento, Mercado Pago, mensageria, email, Docker, proxy, CI/CD, dependencias, testes e documentacao.  
Objetivo de referencia: OWASP ASVS 5 nivel 2, OWASP Top 10, OWASP API Security Top 10 e documentacao oficial do Mercado Pago aplicavel ao fluxo encontrado.

## Sumario executivo

Foram catalogados 40 achados: 5 criticos, 16 altos, 14 medios e 5 baixos. No estado final desta revisao, 32 estao corrigidos, 6 parcialmente corrigidos e 2 pendentes. Os falsos positivos descartados nao entram nessa contagem.

| Severidade | Total | Corrigidos | Parciais | Pendentes |
| --- | ---: | ---: | ---: | ---: |
| Critica | 5 | 4 | 1 | 0 |
| Alta | 16 | 15 | 1 | 0 |
| Media | 14 | 8 | 4 | 2 |
| Baixa | 5 | 5 | 0 | 0 |
| **Total** | **40** | **32** | **6** | **2** |

Esta auditoria reduziu riscos concretos, mas nao certifica que o sistema seja "100% seguro". A verificacao foi local, sem cobrancas, reembolsos ou ataques contra producao e sem acesso ao painel, IAM, banco, backups, observabilidade ou rede reais.

## Arquitetura identificada

- Frontend: Next.js 16.2.10, React 19.2.3, TypeScript, App Router e middleware de navegacao.
- Backend: FastAPI 0.139.0, Pydantic 2.12.5, SQLAlchemy 2.0.46 e Uvicorn.
- Banco principal pretendido: PostgreSQL/Neon via `psycopg2`; ha compatibilidade legada com MySQL. Os testes locais usam banco isolado configurado pelas fixtures.
- Autenticacao: senha bcrypt e JWT HS256 em cookie `HttpOnly`; claims obrigatorias incluem `iss`, `aud`, `jti`, `iat`, `exp` e `session_version`; novos tokens tambem registram `auth_time` para operacoes administrativas sensiveis.
- Perfis: visitante publico, usuario de estabelecimento/tenant e superadministrador.
- Multiestabelecimento: `estabelecimento_id`/`barbearia_id` em recursos; o tenant do JWT e comparado com o cabecalho e aplicado nas consultas.
- Pagamento: Mercado Pago Checkout Pro, com criacao server-side de preferencia e redirecionamento para checkout hospedado. Nao foi encontrado recebimento ou armazenamento de PAN, CVV, validade ou dados brutos de cartao.
- Integracoes adicionais: Meta WhatsApp Cloud API, MegaAPI e email SMTP/Resend.
- Infraestrutura: containers Docker nao-root, Caddy para TLS/reverse proxy e GitHub Actions para teste e deploy por SSH.

Fluxo critico:

```text
Navegador -> Next.js -> FastAPI -> PostgreSQL
                         |
                         +-> cria preferencia Checkout Pro com preco recalculado
                         |
Mercado Pago <- checkout +-> webhook HMAC -> consulta API do provider
                                           -> valida conta/tenant/valor/moeda/referencia
                                           -> maquina de estados do pagamento
                                           -> confirma ou encaminha agendamento para revisao
```

O retorno do navegador informa apenas a experiencia de tela. Ele nao aprova pagamento.

## Modelo de ameacas resumido

Ativos sensiveis:

- credenciais do Mercado Pago e dos canais de mensageria;
- chave de criptografia, pepper, segredo JWT, cookies e sessoes;
- nomes, telefones, emails, agenda e historico de clientes;
- preco, recebedor, estado do pagamento e disponibilidade de horarios;
- privilegios de superadministrador e credenciais de deploy.

Atores e fronteiras de confianca:

- visitante anonimo controlando formularios, IDs, slugs, query strings e frequencia de chamadas;
- usuario autenticado tentando acesso horizontal a outro estabelecimento;
- conta administrativa comprometida tentando acesso vertical;
- navegador, proxy, backend, banco e provedores externos como fronteiras distintas;
- Mercado Pago, Meta, MegaAPI, email, CI/CD e VPS como integracoes externas;
- webhook, URLs de callback, cabecalhos de proxy e respostas do provider como entradas nao confiaveis ate validacao.

Operacoes criticas:

- login, logout, troca de senha e revogacao de sessao;
- gravacao/rotacao de credenciais;
- criacao de agendamento e reserva de horario;
- criacao de preferencia, reconciliacao de pagamento e mudanca de estado;
- cancelamento, reembolso, exclusao de tenant e deploy.

## Metodologia e baseline

Foram usados leitura estatica, rastreamento manual de fluxos e dependencias, testes de regressao, build/typecheck, ESLint, `pip-audit`, `npm audit`, Bandit, `compileall`, busca de padroes de segredo e consulta do historico Git sem imprimir valores. O `AGENTS.md` solicita o knowledge graph `code-review-graph`, mas nenhum dos MCPs citados estava disponivel na sessao; a indisponibilidade foi confirmada antes do fallback para `rg` e leitura direcionada.

Baseline anterior as correcoes:

- backend: 293 testes aprovados, 1.162 avisos;
- frontend: build aprovado;
- lint: 5 erros e 1 aviso preexistentes;
- `npm audit`: 12 vulnerabilidades, sendo 6 altas, 5 medias e 1 baixa;
- `pip-audit`: 29 vulnerabilidades em 10 pacotes;
- Bandit: 1 alerta medio posteriormente descartado e 24 baixos.

Estado final validado:

- backend: 355 testes aprovados, 48 avisos, cobertura total 80,94% e piso de 78% atendido;
- frontend: ESLint sem erros/avisos e build de producao aprovado com typecheck;
- `npm audit --audit-level=low`: 0 vulnerabilidades conhecidas;
- `pip-audit -r requirements.txt`: 0 vulnerabilidades conhecidas;
- Bandit `-ll`: 0 alertas medios ou altos; 22 baixos permanecem para triagem continua;
- `python -m compileall -q app`: aprovado;
- `git diff --check`: aprovado; busca em todo o working tree nao encontrou marcadores de conflito.
- Gitleaks 8.30.1: 322 commits varridos com redaction total; 11 candidatos historicos detectados, incluindo 2 no antigo `backend/.env`, sem exibir valores.

Avisos ainda visiveis: usos de `datetime.utcnow()` restritos a testes, deprecacoes de dependencias (`slowapi`/TestClient) e aviso do Next.js para migrar futuramente `middleware.ts` para a convencao `proxy`.

### Incidente apos git pull

O merge `3ce45dc` trouxe marcadores de conflito versionados em 26 arquivos e mais de 2.000 linhas duplicadas, incluindo `frontend/services/api.ts`. A arvore foi reconstruida a partir do pai auditado `ce17c6c`; as adicoes de marketplace foram reaplicadas de forma compativel, sem mensagens sensiveis do provider e com taxa opcional validada por `Decimal`. O estado final nao contem marcadores, compila e passa pela suite completa.

## Achados corrigidos

| ID | Severidade | CWE / categoria | Componente | Impacto e cenario nao destrutivo | Correcao e evidencia |
| --- | --- | --- | --- | --- | --- |
| C-02 | Critica | CWE-345, API10 | `routes/payments.py`, `webhook_service.py` | Um POST forjado ou uma rota duplicada podia influenciar a confirmacao sem cadeia completa de confianca. | Mantido um webhook canonico; HMAC oficial, janela de 5 min, consulta ao provider e validacao completa. Testes `test_mapped_mercadopago_webhook_requires_signature` e `test_webhook_validates_establishment_webhook_secret`. |
| C-03 | Critica | CWE-602, CWE-840 | `public_booking_service.py`, schemas publicos | O cliente podia tentar enviar estado/preco ou evitar pagamento obrigatorio. | Campos extras sao rejeitados, preco e obrigatoriedade sao obtidos no backend e o estado e imposto pelo servidor. Testes `test_public_booking_rejects_client_controlled_price_and_status` e `test_public_booking_cannot_bypass_required_payment`. |
| C-04 | Critica | CWE-250, CI/CD | Docker e workflows | Montagem do socket Docker/controle excessivo de deploy ampliava um comprometimento para o host. | Socket removido; deploy usa SSH com host key fixada; containers sem root, capabilities ou escrita. Revisado em `docker-compose.yml`, Dockerfiles e `deploy.yml`. |
| C-05 | Critica | CWE-200, CWE-441 | `frontend/services/api.ts`, emails/callbacks | Ausencia de configuracao local podia enviar requisicoes e dados para dominio legado externo. | Fallback operacional alterado para `127.0.0.1`; producao falha sem URLs HTTPS explicitas. Busca final nao encontrou uso operacional do dominio legado. |
| H-01 | Alta | CWE-311, CWE-312 | credenciais de pagamento | Credenciais recuperaveis sem autenticidade ou novamente exibidas aumentavam vazamento e adulteracao. | AES-256-GCM com nonce unico, AAD, versionamento/key ID, keyring e migracao legada; campos write-only e respostas mascaradas. Testes de aleatoriedade, adulteracao, rotacao e mascaramento. |
| H-02 | Alta | CWE-922, ASVS V3 | sessao frontend/backend | JWT em `localStorage` seria extraivel por XSS e persistiria entre tenants. | Sessao em cookie `HttpOnly`, `SameSite=Lax`, `Secure` em producao; frontend guarda apenas metadados de UI e envia credenciais do cookie. Teste `test_session_cookie_has_browser_security_flags`. |
| H-03 | Alta | CWE-256, CWE-521 | senhas e admin | Senha plaintext legada, segredo JWT default ou admin default permitiriam takeover. | Somente bcrypt e aceito; senhas fortes/limite bcrypt; producao exige JWT e admin explicitos. Testes `test_verificar_senha_plaintext_rejeitado` e `test_admin_cannot_create_account_with_unsafe_bcrypt_password`. |
| H-04 | Alta | CWE-204, CWE-352, CWE-613 | login e sessao | Enumeracao, sessao de conta desativada, CSRF por cookie e token antigo apos senha. | Resposta generica, dummy hash, rate limit, validacao de ativo/vencimento, `auth_version`, blacklist de logout e Origin em mutacoes. Testes de conta inativa, CSRF, revogacao e logout. |
| H-05 | Alta | CWE-362, API4 | checkout | Retry apos timeout podia criar preferencias/cobrancas logicas duplicadas. | Chave de idempotencia persistida por operacao, enviada em `X-Idempotency-Key` e reutilizada somente no mesmo retry. Testes de retry, preferencia repetida e cabecalho. |
| H-06 | Alta | CWE-602, CWE-682 | preco e schemas | Preco/status manipulados e float podiam alterar cobranca. | Snapshot server-side do servico, `Decimal`/`Numeric`, moeda BRL e schemas `extra=forbid`. Teste de mass assignment e binding de valor. |
| H-07 | Alta | CWE-345, CWE-639 | webhook/pagamento | Evento valido de outra conta, tenant, agendamento, moeda ou valor podia ser associado incorretamente. | Validacao de payment ID, referencia opaca, metadata, tenant, agendamento, valor, moeda e `collector_id`. Teste parametrizado `test_provider_payment_binding_rejects_cross_context_payload`. |
| H-08 | Alta | CWE-294, CWE-367 | webhook/state machine | Replay, duplicata ou evento fora de ordem podia repetir efeitos ou regredir aprovado. | Evento persistido/idempotente, retry controlado, janela temporal, transicoes permitidas e nao regressao. Testes de replay, duplicidade, retry e evento fora de ordem. |
| H-10 | Alta | CWE-400, CWE-664 | reserva/checkout | Falha deterministica antes do checkout podia manter o horario bloqueado. | Integracao/segredo/valor sao validados antes; falha definitiva cancela pagamento e libera hold; falha incerta preserva hold e idempotencia por 5 min. Testes sem conta e sem webhook secret. |
| H-11 | Alta | CWE-639, CWE-862, API1 | rotas multi-tenant | Troca de IDs/cabecalho podia expor agenda, cliente, servico, pagamento ou credencial de outro tenant. | Tenant do JWT e obrigatorio e comparado ao cabecalho; consultas usam tenant; lookup publico por telefone foi removido. Suites `test_tenant_isolation.py`, cadastros e pagamentos. |
| H-12 | Alta | CWE-306, CWE-345 | Meta, MegaAPI e interno | Webhooks/calls internos sem prova de origem permitiriam spam e comandos falsos. | Assinaturas SHA-256/HMAC, token interno fail-closed, replay/body limits e modo unsigned proibido em producao. Testes de assinatura e payload excessivo. |
| H-13 | Alta | CWE-1104 | dependencias | Bibliotecas com CVEs conhecidas ampliavam XSS/RCE/DoS/supply-chain. | Versoes compativeis atualizadas e lockfile regenerado; Axios removido. `npm audit` e `pip-audit` terminam com zero vulnerabilidades conhecidas. |
| H-14 | Alta | CWE-16, CWE-346 | proxy/configuracao | Cabecalhos `X-Forwarded-*` forjados ou defaults de producao podiam burlar HTTPS/origem. | Proxy headers desativados no Uvicorn ate proxies explicitamente confiaveis; IP real vem de `request.client`; hosts/CORS/proxies/URLs/segredos falham fechados. Teste de HTTPS administrativo. |
| H-15 | Alta | CWE-16, CWE-345 | integracao MP | Salvar token marcava integracao como pronta mesmo sem validacao/segredo de webhook. | Credencial salva fica pendente; checkout exige integracao ativa, validada e com webhook secret. Testes de validacao, permissoes e bloqueio sem secret. |
| H-16 | Alta | CWE-670, CWE-841 | consistencia financeira | Pagamento aprovado tardio, chargeback ou evento terminal repetido podia gerar estado incoerente/email duplicado. | Maquina inclui `charged_back`; aprovado nao regride; conflito tardio vira `payment_review_required`; efeitos so ocorrem em transicao real. Testes de nao regressao e notificacao terminal unica. |
| M-03 | Media | CWE-770 | rate limiting | O storage em memoria nao coordenava limites entre replicas. | Producao agora exige `RATE_LIMIT_STORAGE_URI` Redis/Rediss; Compose inclui Redis isolado e sem fallback silencioso. Teste `test_production_requires_shared_rate_limit_storage`. |
| M-08 | Media | CWE-1104, supply chain | Actions e imagens por tag podiam mudar sem revisao. | GitHub Actions fixadas por commit SHA, imagens Docker por digest e Dependabot semanal configurado para Actions, pip, npm e Docker. |
| M-09 | Media | CWE-778 | auditoria administrativa | Alteracoes criticas nao tinham trilha suficiente. | `AdminAuditLog` registra ator, acao, tenant, recurso, horario, resultado e correlacao, com redaction. Testes de sucesso/falha sem segredo. |
| M-10 | Media | CWE-459, privacidade | exclusao de tenant | Hard delete podia apagar historico financeiro e dificultar investigacao. | Exclusao administrativa virou desativacao/revogacao de sessoes e integracoes, preservando historico e auditoria. |
| M-11 | Media | CWE-200 | notificacoes frontend | Troca de tenant podia manter notificacoes anteriores na memoria/tela. | Hook passou a ser tenant-scoped, limpa dados e descarta respostas async obsoletas. Lint/build validam o contrato. |
| M-12 | Media | CWE-367, CWE-841 | efeitos terminais | Reentrega de aprovado/chargeback podia criar notificacao repetida. | Efeito e emitido somente se a transicao persistida mudou estado. Teste `test_repeated_terminal_status_does_not_duplicate_notifications`. |
| M-13 | Media | CWE-601, CWE-918 | URLs externas | Callback privado, redirect de provider arbitrario ou redirect HTTP podia causar SSRF/open redirect. | Apenas HTTPS publico e hosts oficiais do Mercado Pago; IPs nao globais, userinfo, portas indevidas e redirects HTTP sao recusados. Testes parametrizados de URLs privadas e checkout nao confiavel. |
| M-14 | Media | CWE-613, regra de negocio | Pix/hold | QR/preferencia longa e hold diferente do provider mantinham cobranca e horario inconsistentes. | Hold e `date_of_expiration` sao limitados a no maximo 5 min; expiracao libera slot; pagamento tardio exige reconciliacao/revisao. Teste `test_checkout_expiration_is_capped_at_five_minutes`. |
| L-01 | Baixa | CWE-532 | logs | Token, cookie, payload ou PII poderiam aparecer em logs. | Access log do backend desativado no container, payloads nao sao logados integralmente e redaction cobre campos sensiveis. Testes de logger e auditoria. |
| L-02 | Baixa | CWE-459 | blacklist JWT | Tokens expirados podiam permanecer indefinidamente na blacklist. | Job horario remove registros vencidos pelo indice `expires_at`; teste `test_expired_revoked_tokens_are_purged`. |
| L-03 | Baixa | CWE-682 | tempo | `datetime.utcnow()` obsoleto mantinha risco de semantica temporal ambigua. | Codigo de producao usa `utcnow_naive()` centralizado, preservando compatibilidade com as colunas atuais; busca final em `backend/app` retorna zero ocorrencias. |
| L-04 | Baixa | CWE-16 | documentacao/lockfiles | Instrucoes antigas e lockfile raiz ambiguo favoreciam deploy inseguro. | README, `.env.example`, guia de pagamento e CI atualizados; lockfile vazio da raiz removido. |
| L-05 | Baixa | CWE-798 | scanner de segredos | Nao havia scanner dedicado no pipeline. | Gitleaks foi executado localmente com redaction total e adicionado ao CI com historico completo; os candidatos historicos mantem C-01 aberto ate rotacao e limpeza. |

## Achados parcialmente corrigidos

| ID | Severidade | CWE / categoria | Componente | Estado atual e risco residual | Acao restante |
| --- | --- | --- | --- | --- | --- |
| C-01 | Critica | CWE-798 | Git/segredos | Gitleaks varreu 322 commits com redaction total e detectou 11 candidatos; 2 estao no antigo `backend/.env`. Nenhum valor foi exibido. | Rotacionar tudo que possa ter sido usado, triar os 9 candidatos de docs/fixtures e depois reescrever o historico de forma coordenada. A remocao local nao revoga credenciais externas. |
| H-09 | Alta | CWE-362 | concorrencia de agenda | Criacao/edicao/reagendamento bloqueiam a linha do profissional e revalidam conflito na mesma transacao. Testes impedem conflito sequencial. | Executar teste concorrente real em PostgreSQL staging; SQLite/local nao comprova semantica de `FOR UPDATE` em duas conexoes. Avaliar constraint/slot ledger para defesa adicional. |
| M-01 | Media | CWE-308 | contas administrativas | Mutacoes de credenciais e conta de pagamento exigem autenticacao com no maximo 15 min, mas ainda nao ha MFA. | Implementar WebAuthn/TOTP, recovery codes e usar o segundo fator no step-up antes de troca de credencial ou futuro reembolso. |
| M-02 | Media | CWE-79, CSP | frontend/Caddy | Headers e CSP foram adicionados, mas o script inline estatico de tema ainda requer `unsafe-inline`. Nao recebe entrada do usuario. | Migrar bootstrap de tema para arquivo com nonce/hash e remover `unsafe-inline` apos teste cross-browser. |
| M-04 | Media | API4, disponibilidade | webhook MP | Provider e consultado com timeout e retry correto, mas a consulta ainda ocorre durante a requisicao. | Adotar fila/outbox com ACK rapido, worker idempotente, DLQ e monitoramento antes de escalar horizontalmente. |
| M-07 | Media | CWE-312, CWE-598 | tokens de acao | Tokens de confirmacao sao aleatorios, unicos e expiram, mas permanecem recuperaveis no banco e URLs. | Armazenar hash do token, reduzir retencao e garantir redaction em proxy/analytics/email. Exige migracao compativel. |

## Achados pendentes

| ID | Severidade | CWE / categoria | Componente | Risco | Recomendacao |
| --- | --- | --- | --- | --- | --- |
| M-05 | Media | CWE-639, defesa em profundidade | PostgreSQL | Isolamento depende da aplicacao; nao ha RLS. | Avaliar RLS com `tenant_id` de sessao, usuario DB sem bypass e testes. Nao habilitar sem plano de migracao. |
| M-06 | Media | CWE-16 | schema/migrations | Parte do schema ainda usa `ALTER TABLE`/`create_all` best-effort no startup e engole erros. | Consolidar Alembic, migrations versionadas, dry-run, backup e rollback; em producao, app DB sem privilegio DDL. |

## Falsos positivos descartados

- `0.0.0.0` no Uvicorn: esperado dentro do container; o backend nao publica porta diretamente no Compose e o alerta de bind nao representa autenticacao.
- `dangerouslySetInnerHTML` em `app/layout.tsx`: injeta somente script estatico de tema definido no codigo, sem dados de request/tenant. Continua relacionado ao risco residual de CSP M-02.
- Chave publica do Mercado Pago: e dado publicavel por definicao; nenhum Access Token/Client Secret foi encontrado no bundle ou em variavel `NEXT_PUBLIC_*`.
- Metodo `refund_payment` no adapter: nao ha rota HTTP de reembolso exposta. Duas chamadas ao caminho esperado retornam 404, portanto duplicidade e autorizacao nao sao superficies ativas hoje.
- Strings semelhantes a senha/token em fixtures: valores sinteticos de teste, sem formato/entropia de credencial real e fora da configuracao de producao.

## Testes minimos de seguranca

| # | Cenario solicitado | Evidencia automatizada | Resultado |
| ---: | --- | --- | --- |
| 1 | Preco manipulado pelo frontend | `test_public_booking_rejects_client_controlled_price_and_status` | Passou |
| 2 | Servico de outro estabelecimento | `test_tenant_nao_cria_agendamento_em_outro_tenant` e validacao server-side do bundle | Passou |
| 3 | Acesso a agendamento de outro usuario | `test_tenant_nao_ve_agenda_do_outro` e testes de token publico invalido | Passou |
| 4 | Acesso entre estabelecimentos | `test_tenant_header_mismatch_retorna_403`, `test_tenant_isolation_for_payment_reads` | Passou |
| 5 | Usuario comum em endpoint admin | `test_endpoint_admin_bloqueia_tenant`, testes de credenciais admin | Passou |
| 6 | Webhook sem assinatura | `test_mapped_mercadopago_webhook_requires_signature` | Passou |
| 7 | Webhook com assinatura invalida | `test_webhook_validates_establishment_webhook_secret` | Passou |
| 8 | Webhook repetido | `test_webhook_is_idempotent` | Passou |
| 9 | Webhook antigo/replay | `test_mercadopago_webhook_rejects_stale_signature` | Passou |
| 10 | Webhook de outro estabelecimento | caso tenant/account em `test_provider_payment_binding_rejects_cross_context_payload` | Passou |
| 11 | Evento fora de ordem | `test_approved_payment_does_not_regress_to_pending` | Passou |
| 12 | Aprovado com valor incorreto | `test_webhook_rejects_approved_payment_with_wrong_amount` e caso amount | Passou |
| 13 | Aprovado com referencia incorreta | caso reference em `test_provider_payment_binding_rejects_cross_context_payload` | Passou |
| 14 | Confirmacao via success URL/frontend | `test_block_frontend_confirmation_without_webhook` | Passou |
| 15 | Duas requisicoes criando pagamento | testes de checkout repetido, retry e idempotency header | Passou |
| 16 | Dois clientes no mesmo horario | `test_criar_agendamento_com_conflito` e hold ativo; lock de profissional verificado no codigo | Passou localmente; prova concorrente PostgreSQL pendente em H-09 |
| 17 | Reembolso duplicado | `test_refund_operation_is_not_exposed`, duas chamadas retornam 404 | Passou; funcionalidade nao exposta |
| 18 | Reembolso nao autorizado | `test_refund_operation_is_not_exposed` e ausencia de rota | Passou; funcionalidade nao exposta |
| 19 | SQL Injection | `test_public_booking_rejects_sql_injection_identifier` e ORM parametrizado | Passou |
| 20 | XSS | `test_public_booking_rejects_html_in_customer_name`; React escapa output | Passou |
| 21 | Rate limiting | `test_login_retorna_429_apos_limite` e `test_payment_status_endpoint_is_rate_limited` | Passou |
| 22 | Credenciais nao retornadas | testes de status mascarado, permissoes e edicao sem exposicao | Passou |
| 23 | Logs sem segredos | testes de audit log e logger do servico de integracao | Passou |
| 24 | Expiracao/invalidation de sessao | token expirado, logout blacklist, conta inativa e `auth_version` | Passou |
| 25 | Sessao administrativa antiga em credencial | `test_sensitive_admin_operation_requires_recent_authentication` | Passou |
| 26 | Crescimento da blacklist JWT | `test_expired_revoked_tokens_are_purged` | Passou |

Comandos finais executados:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term --cov-fail-under=78 -q
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt
.\.venv\Scripts\bandit.exe -r app -ll -f txt
.\.venv\Scripts\python.exe -m compileall -q app

cd ..\frontend
npm.cmd audit --audit-level=low
npm.cmd run lint
npm.cmd run build

# Executado a partir do binario oficial em diretorio temporario, com redaction total
cd ..
gitleaks git . --redact=100 --report-format json
```

## Segredos e rotacao

O estado atual foi verificado por padroes sem exibir valores. Nao foi reconhecido segredo real versionado no working tree. O Gitleaks 8.30.1 varreu 322 commits com redaction de 100% e retornou 11 candidatos: 2 no antigo `backend/.env` e 9 em documentacao/fixtures. A presenca historica deve ser tratada como exposicao potencial mesmo sem confirmar quais valores eram reais.

Rotacao manual prioritaria:

1. Revogar e gerar novamente credenciais de banco (`DATABASE_URL`/usuario DB), JWT e admin global.
2. Em cada estabelecimento, revogar Access Token, Client Secret e webhook secret do Mercado Pago; validar novamente a conta no painel Hagendei.
3. Rotacionar Meta/WhatsApp, MegaAPI, SMTP/Resend e `INTERNAL_REMINDER_TOKEN` se alguma dessas credenciais ja existiu nos arquivos.
4. Para `ENCRYPTION_KEY`, primeiro adicionar a chave antiga ao `ENCRYPTION_KEYRING`, ativar uma chave primaria nova, recriptografar e verificar todos os registros; so depois retirar a antiga. Nao substituir a chave cegamente, pois isso torna credenciais existentes irrecuperaveis.
5. Trocar `PAYMENT_CREDENTIALS_PEPPER`; como fingerprints mudam, planejar revalidacao/recalculo controlado.
6. Rotacionar chaves SSH/deploy se houver indicio de que foram armazenadas fora de GitHub Secrets.
7. Depois da revogacao, reescrever o historico com ferramenta apropriada, invalidar caches/forks e exigir novos clones. Nao considerar a reescrita substituta da rotacao.

Use Secret Manager/KMS em producao. O `.env.example` contem somente nomes, defaults locais e instrucoes; `.env.production` continua intencionalmente ausente do repositorio.

## Configuracao segura do Mercado Pago

- Modalidade encontrada: Checkout Pro por preferencia; credenciais privadas ficam somente no backend.
- Configure `BACKEND_PUBLIC_BASE_URL` e `FRONTEND_URL` com HTTPS e hosts controlados.
- Cadastre/permita o webhook canonico `/webhooks/mercadopago`. A preferencia adiciona uma `external_reference` opaca ao `notification_url`; ela serve para lookup, nunca para autorizar.
- Cadastre um webhook secret diferente por integracao quando o modelo da aplicacao Mercado Pago permitir e valide a credencial antes de ativar checkout.
- O backend envia `date_of_expiration` e campos de expiracao da preferencia com limite maximo de 5 minutos. Confirme no sandbox que o checkout exibido respeita esse prazo para todos os meios habilitados.
- Pagamento que chegar depois do hold ou colidir com horario nao e ignorado: fica em `payment_review_required` para reconciliacao humana.
- Monitore respostas 401/400/503 do webhook, eventos em retry, `payment_review_required`, `charged_back` e divergencias de conta/valor/moeda.
- Nao habilite uma rota de reembolso sem autorizacao por tenant, step-up, idempotencia, limite de valor, auditoria e testes dedicados.

Referencias oficiais usadas:

- Criacao de preferencia: https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/create-payment-preference
- Referencia da preferencia: https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-pro/preferences/create-preference/post
- Expiracao: https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/additional-settings/expiration-date
- Webhooks: https://www.mercadopago.com.br/developers/pt/docs/linx/additional-content/your-integrations/notifications/webhooks
- Back URLs: https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/configure-back-urls
- Estornos/cancelamentos: https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/additional-settings/refunds-and-cancellations
- Chargebacks: https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/chargebacks

## Implantacao e operacao

Antes de producao:

1. Preencher segredos em cofre externo e executar o preflight da aplicacao com `APP_ENV=production`.
2. Configurar `ALLOWED_HOSTS`, `TRUSTED_PROXY_IPS`, CORS, dominios do Caddy e todas as URLs HTTPS exatas.
3. Executar migrations Alembic em backup restauravel e retirar DDL do usuario runtime antes de desativar os helpers legados.
4. Aplicar menor privilegio ao banco, backups criptografados, teste de restauracao e retencao definida.
5. Executar o fluxo completo no sandbox: checkout Pix, expiracao de 5 min, duplicata, replay, falha do provider, pagamento tardio, chargeback e reconciliacao.
6. Executar teste concorrente com duas conexoes PostgreSQL para o mesmo profissional/slot.
7. Confirmar no ambiente implantado que o Redis privado do Compose esta saudavel e monitorado; producao falha sem storage Redis/Rediss.
8. Manter o Gitleaks bloqueante, triar os candidatos historicos e adicionar SBOM/assinatura de imagem ao CI; pins SHA/digest e renovacao semanal ja estao configurados.
9. Implementar MFA e alertas para troca de credencial, falhas de assinatura e estados em revisao; o step-up por autenticacao recente ja esta ativo.
10. Definir com juridico/privacidade a base legal, retencao, exclusao, resposta a incidente e atendimento de direitos LGPD.

## Riscos residuais e itens nao verificaveis localmente

- Nao foi realizado pagamento, reembolso ou chamada destrutiva real. O provider foi simulado nos testes.
- Docker CLI nao estava disponivel; imagens/Compose foram revisados estaticamente, sem subir a stack final.
- Nao houve acesso a configuracao real do Neon/PostgreSQL, grants, RLS, backups, firewall, Caddy/VPS, GitHub Environments ou logs.
- Sem credenciais sandbox fornecidas, nao foi possivel comprovar como a UI hospedada do Mercado Pago descreve a expiracao Pix de 5 minutos.
- A semantica concorrente de `SELECT ... FOR UPDATE` precisa de teste em PostgreSQL staging.
- O rate limit compartilhado depende da disponibilidade do Redis; o webhook ainda faz I/O sincrono.
- MFA, hash de confirmation token, RLS e migrations exclusivas por Alembic continuam abertos; o step-up atual reduz, mas nao elimina, o risco administrativo.
- Dependencias podem ganhar novos advisories depois da data desta auditoria; scanners devem rodar continuamente.
- O codigo nao recebe dados brutos de cartao e usa checkout hospedado, mas esta revisao nao concede certificacao PCI DSS.
- Melhorias tecnicas de minimizacao/redaction nao equivalem a conformidade LGPD; retencao, base legal, contratos e processos exigem avaliacao organizacional/juridica.

## Arquivos principais alterados

- `backend/app/security.py`, `routes/auth.py`, `routes/deps.py`: senha, JWT, cookie, revogacao, CSRF e autorizacao.
- `backend/app/services/payments/*`, `routes/payments.py`, modelos de pagamento: criptografia, idempotencia, Checkout Pro, webhook e maquina de estados.
- `backend/app/services/agendamento_service.py`, `public_booking_service.py`, schemas/repositories: preco server-side, tenant, lock e holds.
- `backend/app/routes/whatsapp.py`, `routes/webhooks.py`, `services/webhook_security.py`: assinaturas, replay e limites.
- `backend/app/main.py`, `config.py`, `database.py`, `.env.example`: fail-closed, headers e configuracao.
- `frontend/services/api.ts`, `services/auth.ts`, middleware, hooks e paginas: cookie, contratos e isolamento de cache/UI.
- Dockerfiles, `docker-compose.yml`, `Caddyfile` e `.github/workflows/*`: hardening e supply chain.
- `backend/tests/test_security_audit.py`, `test_payments_module.py` e suites existentes: regressao de seguranca.
- `README.md`, `docs/admin-payment-credentials.md` e este relatorio: operacao e resposta manual.
