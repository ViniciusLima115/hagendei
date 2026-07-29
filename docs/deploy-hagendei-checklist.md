# Checklist de deploy — domínio hagendei.com

Passos manuais (fora do acesso do assistente) para colocar o sistema no ar em
`app.hagendei.com`, apontando para o servidor de produção atual. Siga na
ordem — pular a Etapa 4 (rebuild) é o erro mais comum: o site parece "no ar"
(DNS e TLS ok) mas o frontend continua chamando a API antiga e o backend
rejeita as requisições do novo domínio.

**Decisão de arquitetura:** `hagendei.com` (raiz) fica reservado para a
landing de vendas (projeto/deploy separado, fora deste repositório — ainda
não decidido onde vai ficar hospedada). O sistema deste repositório (o app
propriamente dito: login, gestão, agenda, agendamento público etc.) fica em
`app.hagendei.com`, porque a rota raiz (`/`) deste Next.js já é conteúdo
autenticado do próprio sistema — colocar o sistema na raiz do domínio
entraria em conflito direto com a landing.

## 1. DNS (Hostinger, ou onde o domínio estiver gerenciado)

Registros `A` necessários na zona DNS de `hagendei.com`, apontando para o IP
público do servidor onde o Caddy roda hoje:

| Tipo | Host | Valor | TTL |
|------|------|-------|-----|
| A | `app.hagendei.com` | `<IP do servidor>` | 3600 (ou automático) |
| A | `api.hagendei.com` | `<IP do servidor>` | 3600 (ou automático) |

O registro `A` de `hagendei.com` (`@`, raiz) fica em aberto até a landing de
vendas ter hospedagem decidida — não aponte para o servidor deste sistema
sem antes configurar um bloco de site próprio no `Caddyfile` para ele (ver
nota abaixo), ou o Caddy pode acabar servindo o sistema também na raiz por
engano assim que emitir certificado para esse hostname.

Se o frontend também deve responder em `www.hagendei.com` (redirecionando
para a landing, por exemplo), isso é definido junto com a decisão de
hospedagem da landing, não faz parte deste checklist.

## 2. Variáveis de ambiente no servidor de produção

Existem **dois arquivos `.env` diferentes** no servidor — os dois precisam ser
atualizados, não só um:

**a) `.env` na raiz do projeto** (usado pelo `docker-compose.yml` para o Caddy
e para o *build* do frontend):

```
APP_DOMAIN=app.hagendei.com
API_DOMAIN=api.hagendei.com
NEXT_PUBLIC_API_URL=https://api.hagendei.com
```

**b) `backend/.env.production`** (usado em runtime pelo backend — controla CORS
e os links públicos gerados em mensagens/e-mails):

```
APP_ENV=production
CORS_ALLOWED_ORIGINS=https://app.hagendei.com
FRONTEND_URL=https://app.hagendei.com
BACKEND_PUBLIC_BASE_URL=https://api.hagendei.com
BOOKING_PUBLIC_BASE_URL=https://app.hagendei.com
EMAIL_ACTION_BASE_URL=https://app.hagendei.com
ALLOWED_HOSTS=api.hagendei.com,127.0.0.1
TRUSTED_PROXY_IPS=<CIDR_DA_REDE_DOCKER_DO_CADDY>
REMINDER_MAX_ATTEMPTS=3
REMINDER_RETRY_MINUTES=5
```

O Compose também força `APP_ENV=production` no container para impedir que um
arquivo copiado do exemplo suba silenciosamente com cookie inseguro, documentação
aberta ou MFA opcional. Mantenha a variável explícita no arquivo para que
comandos administrativos executados fora do Compose usem as mesmas validações.
Em produção, o backend falha ao iniciar se qualquer URL pública acima não usar
HTTPS ou se uma configuração crítica estiver ausente.

`EMAIL_ACTION_BASE_URL` merece atenção separada: ela tem prioridade sobre
`BOOKING_PUBLIC_BASE_URL` na montagem dos botões enviados por e-mail. Se ela
continuar apontando para `127.0.0.1`, o site funciona, mas os clientes recebem
links quebrados.

As duas variáveis `REMINDER_*` são opcionais. Os valores acima fazem cada
lembrete tentar no máximo três vezes; as duas primeiras falhas reagendam em
5 e 10 minutos. `REMINDER_MAX_ATTEMPTS` aceita de 1 a 10 e
`REMINDER_RETRY_MINUTES` define a espera base de 1 a 60 minutos. Com mais
tentativas, o intervalo continua dobrando, mas nunca ultrapassa 60 minutos.

`ALLOWED_HOSTS` é obrigatório em produção e é validado contra o header `Host`
real de cada requisição (`TrustedHostMiddleware`) — diferente do CORS, que só
afeta chamadas feitas por um navegador, isso bloqueia **qualquer** requisição
(inclusive `curl`) se o domínio não estiver na lista. Sem essa variável
atualizada, o backend inteiro responde `400 Invalid host header` para tudo,
incluindo os próprios comandos de verificação abaixo. Note que `ALLOWED_HOSTS`
lista apenas o host da **API** (`api.hagendei.com`) — o backend nunca recebe
requisições com `Host: app.hagendei.com`, então esse hostname não entra aqui.

**Importante:** inclua `127.0.0.1` na lista mesmo em produção — o healthcheck
interno do container do backend (`docker-compose.yml`) chama
`http://127.0.0.1:8000/health` de dentro do próprio container, com header
`Host: 127.0.0.1`. O fallback padrão do backend (quando `ALLOWED_HOSTS` não
está definido) já inclui `127.0.0.1`, mas ao definir a variável explicitamente
esse fallback deixa de valer — sem incluir `127.0.0.1` na lista, o healthcheck
passa a falhar, o container do backend nunca fica "healthy", e o Caddy (que
depende de `backend: condition: service_healthy` no `docker-compose.yml`)
nunca sobe — o site fica fora do ar por completo, não só a API.

`TRUSTED_PROXY_IPS` não é a mesma configuração que `ALLOWED_HOSTS`. O backend
recebe as conexões do IP do container Caddy, não de `127.0.0.1`. Descubra o
subnet da rede do projeto no servidor e informe esse CIDR:

```bash
docker network ls --filter name=barbershop-chatbot_default
docker network inspect barbershop-chatbot_default \
  --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
```

Exemplo de resultado: `172.20.0.0/16`. Nesse caso, use
`TRUSTED_PROXY_IPS=172.20.0.0/16`. Confirme o nome real exibido pelo primeiro
comando; ele muda se `COMPOSE_PROJECT_NAME` ou o diretório do projeto mudar.
Não use `*` e não mantenha apenas `127.0.0.1`: sem confiar no proxy correto,
todos os clientes aparentam ter o mesmo IP do Caddy e podem compartilhar
indevidamente o mesmo limite de requisições.

## 3. Gates de banco, backup e segredos

O deploy só pode seguir se o workflow **Security and Tests** estiver verde para
o mesmo SHA. O workflow de deploy usa exatamente esse SHA e não deve ser
disparado diretamente por um `push` sem testes.

No backend, o workflow cria um PostgreSQL descartável, aplica
`alembic upgrade head` desde um banco vazio e exige `alembic check` sem drift
antes de rodar a suíte.

O gate do frontend executa separadamente:

- `npm audit --omit=dev --audit-level=high`, que bloqueia vulnerabilidades
  altas/críticas nas dependências carregadas em produção;
- `npm run lint`;
- `npm run build`.

Há uma exceção temporária e restrita à árvore de desenvolvimento: o relatório
completo do `npm audit` ainda aponta advisories de `brace-expansion`/`minimatch`
usados pelo tooling de lint. A versão corretiva atual quebra a API esperada
pelo ESLint 9 e seus plugins, enquanto o ESLint 10 ainda não satisfaz os
peer-dependencies desses plugins. Isso não remove nem suaviza o gate de
runtime acima, e lint/build continuam obrigatórios. Revise esta exceção a cada
atualização do ESLint/plugins e remova-a assim que houver uma combinação
compatível; registre o resultado do audit completo no relatório de release.

### 3.1 Alembic e banco existente

Use uma URL **direta** do PostgreSQL/Neon para migrações. Não use o endpoint
PgBouncer `-pooler` para `alembic` ou `pg_dump`.

```bash
cd backend
python -m alembic heads
python -m alembic current
```

- Banco novo e vazio: execute `python -m alembic upgrade head` e depois
  `python -m alembic check`.
- Banco existente com uma revisão exibida: crie uma cópia de staging, execute
  `upgrade head` e `check` nela primeiro. Só repita na produção após validar os
  fluxos críticos.
- Banco existente com tabelas, mas `alembic current` vazio: **não** rode
  `upgrade head` e **não** use `stamp head`. Esse banco antecede o controle de
  versão e precisa de baseline. Na cópia restaurada de staging, confirme que o
  schema corresponde ao legado anterior à revisão `0003`; somente então rode:

```bash
python -m alembic stamp 0002
python -m alembic upgrade 0004
```

O `stamp` apenas registra a baseline; ele não cria nem corrige tabelas. Se a
cópia não passar, interrompa o lançamento e corrija a divergência antes de
tocar na produção. Registre a revisão anterior, a nova revisão e a duração da
migração no relatório do deploy.

Depois de chegar à `0004` na cópia e antes de aplicar a `0005`, estes três
resultados precisam ser zero:

```sql
SELECT count(*) FROM payment_oauth_states
WHERE establishment_id IS NULL OR state IS NULL;

SELECT count(*) FROM reminder_jobs r
LEFT JOIN estabelecimentos e ON e.id = r.estabelecimento_id
WHERE r.estabelecimento_id IS NULL OR e.id IS NULL;

SELECT count(*) FROM (
  SELECT agendamento_id, tipo
  FROM reminder_jobs
  GROUP BY agendamento_id, tipo
  HAVING count(*) > 1
) duplicados;
```

A reconciliação descarta estados OAuth sem tenant/estado e jobs de lembrete
órfãos; para lembretes duplicados, mantém o menor `id`. Se qualquer consulta
retornar linhas, exporte e corrija esses registros antes de migrar. A revisão
também altera tipos, índices, constraints e FKs sem `CONCURRENTLY`; agende uma
janela de manutenção e meça o tempo na cópia restaurada antes da produção.

Com o preflight limpo:

```bash
python -m alembic upgrade head
python -m alembic check
```

### 3.2 Backup e restauração

Antes de cada migração:

- crie uma branch/snapshot do Neon no ponto imediatamente anterior ao deploy e
  registre a janela de restauração disponível no plano;
- gere também um `pg_dump` criptografado usando conexão direta, com retenção e
  acesso definidos;
- restaure o backup em outro banco/branch e execute `alembic current`,
  `alembic check` e os smoke tests. Um backup nunca restaurado não conta como
  recuperação validada;
- defina RPO/RTO e a pessoa responsável por autorizar uma restauração;
- mantenha cópia recuperável de `ENCRYPTION_KEY`, `ENCRYPTION_KEYRING` e
  `PAYMENT_CREDENTIALS_PEPPER` em cofre separado. Sem essas chaves, o banco
  restaurado não recupera as credenciais de pagamento cifradas.

### 3.3 Rotação de segredos

Antes do primeiro lançamento, confirme no provedor — não apenas no arquivo
local — a rotação de todo segredo que possa ter aparecido no histórico Git:
banco, JWT, conta administrativa, Mercado Pago, Meta/WhatsApp, MegaAPI, e-mail
e chave SSH de deploy. Grave apenas os valores novos no cofre de produção,
revogue os antigos e execute novamente o scanner de segredos. Nunca imprima os
valores no log do deploy.

## 4. Rebuild — não é só reiniciar

`NEXT_PUBLIC_API_URL` é um *build arg* do frontend (`docker-compose.yml`,
serviço `frontend`, seção `build.args`): ele é gravado dentro dos arquivos
estáticos do Next.js no momento do build, não é lido em runtime. Um simples
`restart` do container **não** aplica esse valor novo — é necessário reconstruir
as imagens:

```bash
cd /caminho/do/projeto/no/servidor
docker compose up -d --build --remove-orphans --wait --wait-timeout 180
```

**Não** use `-f docker-compose.yml -f docker-compose.prod.yml` juntos — o
`docker-compose.prod.yml` já é só um `include: [docker-compose.yml]`, e passar
os dois arquivos via `-f` faz o Compose carregar o mesmo conteúdo duas vezes,
o que quebra a validação (`items at 0 and 1 are equal` em campos de lista como
`security_opt`) e o comando falha com erro antes de reconstruir qualquer
coisa. O comando acima (`docker compose up -d --build`, sem `-f`) é o mesmo
usado por `scripts/deploy.sh` neste repositório e é o jeito certo de rodar.

Isso reconstrói `frontend` e `backend` com as variáveis novas e reinicia todos
os serviços (incluindo o Caddy, que já lê `{$APP_DOMAIN}`/`{$API_DOMAIN}`
diretamente do `Caddyfile` sem precisar de nenhuma mudança de código) em uma
única passada — não precisa rodar `restart` separadamente depois.

O Caddy emite o certificado TLS automaticamente via Let's Encrypt assim que o
DNS resolver para o IP correto — não é necessário configurar certificado
manualmente.

## 5. Verificação

- [ ] `dig app.hagendei.com` e `dig api.hagendei.com` resolvem para o IP do servidor.
- [ ] `curl -I https://app.hagendei.com` retorna `200` (ou redirect esperado) com
      certificado válido.
- [ ] `curl -fsS https://api.hagendei.com/health` retorna o JSON esperado com
      certificado válido.
- [ ] `curl -I https://api.hagendei.com/docs` e `/openapi.json` retornam `404`
      quando a documentação está desabilitada, como recomendado.
- [ ] Um preflight com `Origin: https://app.hagendei.com` recebe
      `Access-Control-Allow-Origin`; uma origem não autorizada não recebe.
- [ ] Abrir `https://app.hagendei.com` num navegador (não só `curl`) e confirmar que
      a página carrega dados reais (ex.: login funciona, uma página pública de
      agendamento carrega horários) — isso testa a chamada real do browser para
      a API, que é onde um CORS mal configurado aparece e que um `curl` direto
      não pega.
- [ ] Abrir o DevTools do navegador (aba Network/Console) na página carregada e
      confirmar que não há erros de CORS nem chamadas ainda apontando para o
      domínio antigo.
- [ ] Criar um agendamento de staging e validar os links reais de confirmação,
      reagendamento e e-mail; nenhum deles pode conter `localhost` ou
      `127.0.0.1`.
- [ ] Confirmar no log do backend que o scheduler iniciou. O processamento dos
      lembretes WhatsApp roda a cada minuto; a rota autenticada
      `POST /internal/reminders/process` permanece disponível para operação
      manual controlada.
- [ ] Monitorar o backlog sem imprimir dados pessoais:
      `SELECT status, count(*) FROM reminder_jobs GROUP BY status;`. Alertar se
      existirem jobs vencidos em `pendente` ou crescimento de `falha`.
- [ ] Conferir `docker compose ps` e `docker compose logs --since=10m`; não deve
      haver container `unhealthy`, traceback, falha de migração ou erro de
      webhook/pagamento.

Uma falha de envio mantém o job como `pendente` e agenda a próxima tentativa
com backoff exponencial. Ao atingir `REMINDER_MAX_ATTEMPTS`, o job passa para
`falha`. Trate jobs `pendente` vencidos e qualquer crescimento de `falha` como
alerta operacional; só faça reprocessamento manual depois de diagnosticar o
provedor, para evitar envio duplicado.

## Troubleshooting

- **Página carrega mas nenhum dado aparece / erro de CORS no console do
  navegador**: `CORS_ALLOWED_ORIGINS` em `backend/.env.production` não inclui o
  domínio novo, ou o backend não foi reiniciado depois de editar esse arquivo —
  rode novamente o `up -d --build` da Etapa 3.
- **Frontend ainda chama a URL antiga da API**: o `NEXT_PUBLIC_API_URL` foi
  atualizado no `.env` mas as imagens não foram reconstruídas — `docker compose
  up -d --build` sem o `--build` não é suficiente, o cache da imagem antiga
  seria reaproveitado.
- **Links de confirmação/reagendamento enviados por WhatsApp/e-mail apontam
  para o domínio antigo ou localhost**: `BOOKING_PUBLIC_BASE_URL` ou
  `EMAIL_ACTION_BASE_URL` em `backend/.env.production` não foi atualizado.
- **`400 Invalid host header` em qualquer requisição, inclusive `curl -I
  https://api.hagendei.com/docs`**: `ALLOWED_HOSTS` em
  `backend/.env.production` ainda não inclui `api.hagendei.com` — atualize e
  rode o `up -d --build` da Etapa 3 novamente.
- **Site inteiro fora do ar depois do `up -d --build` (Caddy nunca inicia,
  não só a API dando erro)**: verifique `docker compose ps` — se o container
  `backend` está com status diferente de `healthy` (ex. `unhealthy` ou preso em
  `starting`), o `ALLOWED_HOSTS` provavelmente foi definido sem incluir
  `127.0.0.1`, e o healthcheck interno do container está falhando. Corrija
  `ALLOWED_HOSTS=api.hagendei.com,127.0.0.1` em `backend/.env.production` e
  rode o `up -d --build` novamente — o Caddy só sobe depois que o backend
  reportar `healthy`.

## Quando a landing de vendas for definida

Quando decidir onde a landing de `hagendei.com` (raiz) vai ficar hospedada:

- **Se for no mesmo servidor** (outro container/processo atrás do mesmo
  Caddy): adicionar um novo bloco de site no `Caddyfile` para `hagendei.com`
  (e opcionalmente `www.hagendei.com`) apontando (`reverse_proxy`) para o
  serviço da landing, e criar/ajustar o registro `A` de `hagendei.com` para
  o IP deste servidor.
- **Se for em outro provedor** (Vercel, Hostinger website builder, outra
  VPS etc.): apontar o registro `A` (ou `CNAME`) de `hagendei.com` para lá,
  sem tocar em nada deste `Caddyfile` — os domínios `app.` e `api.` deste
  sistema continuam intactos independente de onde a landing morar.
