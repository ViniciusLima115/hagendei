# Hagendei

Plataforma multi-tenant de agendamento para negocios e profissionais. O sistema inclui painel operacional, pagina publica por estabelecimento, notificacoes e pagamento antecipado via Mercado Pago Checkout Pro.

## Arquitetura

- `frontend/`: Next.js 16 e React 19, servido na porta `3000`.
- `backend/`: FastAPI, SQLAlchemy e PostgreSQL/Neon, servido na porta `8000`.
- `Caddyfile`: terminacao TLS e proxy reverso em producao.
- Mercado Pago: credenciais isoladas por estabelecimento e criptografadas no banco.

O backend e a autoridade para autenticacao, tenant, preco, disponibilidade e estado do pagamento. O frontend nunca confirma pagamento por retorno do navegador.

## Requisitos

- Python 3.13
- Node.js 22 e npm
- PostgreSQL 15+ ou Neon

## Desenvolvimento local

Backend, em PowerShell:

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Preencha `DATABASE_URL`, `JWT_SECRET`, `ENCRYPTION_KEY`, `PAYMENT_CREDENTIALS_PEPPER`, `ADMIN_USUARIO` e `ADMIN_SENHA` em `backend/.env`. Gere valores independentes; nunca reutilize senha, JWT, chave de criptografia e pepper.

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, em outro terminal:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Enderecos locais:

- Aplicacao: `http://127.0.0.1:3000`
- API: `http://127.0.0.1:8000`
- Login: `http://127.0.0.1:3000/login`
- Agendamento publico: `http://127.0.0.1:3000/{slug}`

Swagger fica desabilitado por padrao. Para uso local, defina `DOCS_ENABLED=true` e credenciais proprias; nao exponha a documentacao em producao sem necessidade.

## Autenticacao e tenants

O login cria um cookie `HttpOnly`, `SameSite=Lax` e `Secure` em producao. O JWT inclui emissor, audiencia, `jti`, expiracao e versao de sessao. Desativar uma conta ou trocar a senha revoga as sessoes anteriores.

O `X-Estabelecimento-Id` e apenas contexto de requisicao: o backend sempre compara esse valor com o tenant assinado no token. Rotas administrativas globais exigem papel `admin` ou `super_admin`.

## Mercado Pago

1. O administrador salva as credenciais no estabelecimento.
2. O backend cifra o payload com AES-256-GCM; segredos sao somente de escrita na API.
3. Use `Validar conexao`. Uma integracao nao validada nao pode abrir checkout.
4. Cadastre no Mercado Pago o webhook HTTPS `https://SEU_DOMINIO_API/webhooks/mercadopago` e salve a chave secreta correspondente.
5. O backend valida `x-signature`, rejeita replay, consulta o pagamento na API do provedor e compara referencia, tenant, agendamento, valor, moeda e conta recebedora.

O checkout usa idempotencia e reserva a vaga por no maximo cinco minutos. O retorno do navegador serve apenas para navegacao; aprovacao depende do provedor. Nao execute pagamentos ou estornos reais durante testes automatizados.

Mais detalhes: `docs/admin-payment-credentials.md` e `docs/pagamento-adiantado-mercado-pago.md`.

## Rotacao de chaves

Para trocar a chave de credenciais sem perder dados:

1. Mova a chave atual para `ENCRYPTION_KEYRING`, associada ao identificador antigo.
2. Defina um novo `ENCRYPTION_KEY_ID` e uma nova `ENCRYPTION_KEY` de 32 bytes.
3. Reinicie, valide as integracoes e grave novamente cada credencial para cifra-la com a chave nova.
4. Remova a chave antiga somente depois de confirmar que nenhum registro depende dela e de testar o backup.

Trocar `JWT_SECRET` invalida todas as sessoes. Segredos que ja entraram no Git devem ser revogados no provedor antes de qualquer reescrita de historico.

## Testes e verificacoes

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt
.\.venv\Scripts\python.exe -m bandit -r app

cd ..\frontend
npm run lint
npm run build
npm audit --omit=dev
```

O relatorio de seguranca e os riscos residuais ficam em `SECURITY_AUDIT.md`.

## Producao

Use um cofre de segredos e um arquivo local `backend/.env.production` fora do Git. `APP_ENV=production` faz o backend falhar ao iniciar se configuracoes essenciais estiverem ausentes ou inseguras.

```powershell
$env:APP_DOMAIN="app.seudominio.com"
$env:API_DOMAIN="api.seudominio.com"
$env:NEXT_PUBLIC_API_URL="https://api.seudominio.com"
docker compose up -d --build
```

Antes de publicar:

- configure HTTPS, `ALLOWED_HOSTS`, `TRUSTED_PROXY_IPS` e CORS com origens exatas;
- mantenha docs, bearer token e webhooks sem assinatura desabilitados;
- aplique migracoes e teste restauracao de backup em staging;
- restrinja acesso ao banco, ao host Docker e ao painel administrativo;
- configure alertas para falhas de webhook, divergencias de pagamento e eventos `payment_review_required`;
- rode testes e auditorias de dependencia em CI.
