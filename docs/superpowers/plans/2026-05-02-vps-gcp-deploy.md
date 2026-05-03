# VPS GCP Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configurar uma VM Google Compute Engine do zero com Docker Compose + Caddy, deploy automático via webhook do GitHub.

**Architecture:** FastAPI (backend) + Next.js (frontend) + Caddy (reverse proxy/SSL) rodam como containers Docker Compose numa VM e2-small Ubuntu 22.04. Um quarto container com `adnanh/webhook` recebe POST do GitHub e executa `git pull && docker compose up -d --build` na VM.

**Tech Stack:** Docker, Docker Compose, Caddy, Python 3.11-slim, Node 20-alpine, adnanh/webhook, Google Compute Engine, Let's Encrypt (via Caddy)

---

## Arquivos a Criar/Modificar

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `backend/Dockerfile` | Criar | Build e run do FastAPI |
| `frontend/Dockerfile` | Criar | Build e run do Next.js |
| `webhook/Dockerfile` | Criar | Container webhook com docker CLI + git |
| `webhook/hooks.json` | Criar | Configuração do adnanh/webhook |
| `scripts/deploy.sh` | Criar | Script executado pelo webhook na VM |
| `docker-compose.yml` | Criar | Orquestra os 4 containers |
| `Caddyfile` | Criar | Roteamento + SSL automático |

---

## Task 1: Dockerfile do Backend (FastAPI)

**Files:**
- Create: `backend/Dockerfile`

- [ ] **Step 1: Criar `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Testar build local**

```bash
cd backend
docker build -t barbearia-backend .
```

Esperado: `Successfully built <id>` sem erros.

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile
git commit -m "feat: adicionar Dockerfile do backend FastAPI"
```

---

## Task 2: Dockerfile do Frontend (Next.js)

**Files:**
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Criar `frontend/Dockerfile`**

Next.js 16 com output standalone para imagem enxuta:

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 2: Habilitar output standalone no Next.js**

Editar `frontend/next.config.ts`:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

- [ ] **Step 3: Testar build local**

```bash
cd frontend
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.virtualbarber.shop -t barbearia-frontend .
```

Esperado: `Successfully built <id>` sem erros.

- [ ] **Step 4: Commit**

```bash
git add frontend/Dockerfile frontend/next.config.ts
git commit -m "feat: adicionar Dockerfile do frontend Next.js com output standalone"
```

---

## Task 3: Container Webhook

**Files:**
- Create: `webhook/Dockerfile`
- Create: `webhook/hooks.json`

- [ ] **Step 1: Criar `webhook/Dockerfile`**

Imagem com docker CLI + git + binário do webhook:

```dockerfile
FROM docker:27-cli

RUN apk add --no-cache git bash curl

RUN WEBHOOK_VERSION=2.8.1 && \
    wget -qO /usr/local/bin/webhook \
    https://github.com/adnanh/webhook/releases/download/${WEBHOOK_VERSION}/webhook-linux-amd64 && \
    chmod +x /usr/local/bin/webhook

WORKDIR /app

EXPOSE 9000
CMD ["webhook", "-hooks", "/hooks/hooks.json", "-port", "9000", "-verbose"]
```

- [ ] **Step 2: Criar `webhook/hooks.json`**

```json
[
  {
    "id": "deploy",
    "execute-command": "/hooks/deploy.sh",
    "command-working-directory": "/app",
    "pass-environment-to-command": [
      {
        "source": "entire-payload",
        "envname": "WEBHOOK_PAYLOAD"
      }
    ],
    "trigger-rule": {
      "and": [
        {
          "match": {
            "type": "payload-hmac-sha256",
            "secret": "",
            "parameter": {
              "source": "header",
              "name": "X-Hub-Signature-256"
            }
          }
        },
        {
          "match": {
            "type": "value",
            "value": "refs/heads/main",
            "parameter": {
              "source": "payload",
              "name": "ref"
            }
          }
        }
      ]
    }
  }
]
```

> **Nota:** o campo `"secret": ""` será preenchido pelo Docker Compose via variável de ambiente `WEBHOOK_SECRET` — veja Task 4.

- [ ] **Step 3: Commit**

```bash
git add webhook/
git commit -m "feat: adicionar container webhook para deploy automático"
```

---

## Task 4: Script de Deploy

**Files:**
- Create: `scripts/deploy.sh`

- [ ] **Step 1: Criar `scripts/deploy.sh`**

```bash
#!/bin/bash
set -e

REPO_DIR="/home/deploy/barbearia-chatbot"

echo "[deploy] $(date): iniciando deploy..."
cd "$REPO_DIR"
git pull origin main
docker compose up -d --build
echo "[deploy] $(date): deploy concluído."
```

- [ ] **Step 2: Tornar executável**

```bash
chmod +x scripts/deploy.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat: adicionar script de deploy para webhook"
```

---

## Task 5: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Criar `docker-compose.yml`**

```yaml
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - backend
      - frontend
    restart: unless-stopped

  backend:
    build: ./backend
    env_file:
      - ./backend/.env.production
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_URL: https://api.virtualbarber.shop
    restart: unless-stopped

  webhook:
    build: ./webhook
    environment:
      - WEBHOOK_SECRET=${WEBHOOK_SECRET}
    volumes:
      - ./scripts/deploy.sh:/hooks/deploy.sh:ro
      - ./webhook/hooks.json:/hooks/hooks.json:ro
      - /var/run/docker.sock:/var/run/docker.sock
      - /home/deploy/barbearia-chatbot:/home/deploy/barbearia-chatbot
    restart: unless-stopped

volumes:
  caddy_data:
  caddy_config:
```

- [ ] **Step 2: Criar `.env.example` na raiz do projeto** (para documentar a variável do webhook)

```bash
cat >> .env.example << 'EOF'

# Webhook de deploy automático
WEBHOOK_SECRET=gere-um-token-forte-aqui
EOF
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: adicionar docker-compose.yml com caddy, backend, frontend e webhook"
```

---

## Task 6: Caddyfile

**Files:**
- Create: `Caddyfile`

- [ ] **Step 1: Criar `Caddyfile`**

```caddyfile
virtualbarber.shop {
    reverse_proxy frontend:3000
}

api.virtualbarber.shop {
    @deploy path /deploy
    reverse_proxy @deploy webhook:9000

    reverse_proxy backend:8000
}
```

- [ ] **Step 2: Commit**

```bash
git add Caddyfile
git commit -m "feat: adicionar Caddyfile com roteamento e SSL automático"
```

---

## Task 7: Criar VM no Google Cloud (Browser)

> **Ação no browser:** acessar console.cloud.google.com

- [ ] **Step 1: Criar projeto GCP**
  - Acesse `console.cloud.google.com`
  - Menu superior → "Select a project" → "New Project"
  - Nome: `barbearia-chatbot` (ou similar)
  - Clique "Create"

- [ ] **Step 2: Criar instância Compute Engine**
  - Menu → Compute Engine → VM Instances → "Create Instance"
  - **Nome:** `barbearia-vm`
  - **Região:** `southamerica-east1` (São Paulo) — ou `us-central1` se quiser mais barato
  - **Zona:** `southamerica-east1-b`
  - **Machine type:** `e2-small` (2 vCPU, 2 GB)
  - **Boot disk:** Ubuntu 22.04 LTS, 20 GB SSD
  - **Firewall:** marcar "Allow HTTP traffic" e "Allow HTTPS traffic"
  - Clique "Create"

- [ ] **Step 3: Anotar o IP externo**

  Após criar, o IP externo aparece na lista de instâncias. Anote — será usado no DNS.

- [ ] **Step 4: Abrir firewall para portas 80 e 443 (se não habilitado no passo anterior)**
  - VPC Network → Firewall → "Create Firewall Rule"
  - Portas TCP: 80, 443

---

## Task 8: Configurar DNS

> **Ação no painel do registrador de domínio** (onde `virtualbarber.shop` está registrado)

- [ ] **Step 1: Criar registro A para o domínio raiz**
  - Tipo: `A`
  - Nome: `@` (ou `virtualbarber.shop`)
  - Valor: `<IP externo da VM>`
  - TTL: 300 (5 min)

- [ ] **Step 2: Criar registro A para subdomínio da API**
  - Tipo: `A`
  - Nome: `api`
  - Valor: `<IP externo da VM>`
  - TTL: 300

- [ ] **Step 3: Verificar propagação**

```bash
# Rodar do seu Mac, aguardar até retornar o IP da VM
dig virtualbarber.shop A +short
dig api.virtualbarber.shop A +short
```

Esperado: ambos retornam o IP externo da VM.

---

## Task 9: Configurar VM via SSH

- [ ] **Step 1: Conectar via SSH**

  No GCP Console → Compute Engine → VM Instances → botão SSH da instância.  
  Ou via terminal:
  ```bash
  gcloud compute ssh barbearia-vm --zone southamerica-east1-b
  ```

- [ ] **Step 2: Instalar Docker**

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

- [ ] **Step 3: Verificar instalação**

```bash
docker --version
docker compose version
```

Esperado: versões recentes do Docker e Docker Compose plugin.

- [ ] **Step 4: Criar usuário de deploy**

```bash
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG docker deploy
```

- [ ] **Step 5: Configurar SSH key para git (GitHub)**

```bash
sudo -u deploy ssh-keygen -t ed25519 -C "deploy@barbearia-vm" -f /home/deploy/.ssh/id_ed25519 -N ""
sudo cat /home/deploy/.ssh/id_ed25519.pub
```

Copiar a chave pública e adicionar no GitHub:  
Settings → SSH and GPG keys → New SSH key → colar e salvar.

- [ ] **Step 6: Clonar o repositório**

```bash
sudo -u deploy bash -c "
  cd /home/deploy
  git clone git@github.com:<usuario>/<repo>.git barbearia-chatbot
"
```

- [ ] **Step 7: Criar arquivo de variáveis do backend**

```bash
sudo -u deploy bash -c "
  cp /home/deploy/barbearia-chatbot/backend/.env.example /home/deploy/barbearia-chatbot/backend/.env.production
"
sudo nano /home/deploy/barbearia-chatbot/backend/.env.production
```

Preencher com os valores reais:
```
APP_ENV=production
DATABASE_URL=<neon-connection-string>
JWT_SECRET=<segredo-forte-gerado-com-openssl-rand-hex-32>
ENCRYPTION_KEY=<chave-fernet>
CORS_ALLOWED_ORIGINS=https://virtualbarber.shop
FRONTEND_URL=https://virtualbarber.shop
BACKEND_PUBLIC_BASE_URL=https://api.virtualbarber.shop
BOOKING_PUBLIC_BASE_URL=https://virtualbarber.shop
MERCADOPAGO_WEBHOOK_SECRET=<valor>
MERCADOPAGO_WEBHOOK_TOKEN=<valor>
INTERNAL_REMINDER_TOKEN=<valor>
EMAIL_FROM=noreply@virtualbarber.shop
SMTP_HOST=<smtp>
SMTP_PORT=587
SMTP_USER=<usuario>
SMTP_PASSWORD=<senha>
DOCS_USER=admin
DOCS_PASS=<senha-forte>
```

- [ ] **Step 8: Criar arquivo `.env` na raiz (para WEBHOOK_SECRET)**

```bash
sudo -u deploy bash -c "
  cd /home/deploy/barbearia-chatbot
  echo 'WEBHOOK_SECRET='$(openssl rand -hex 32) > .env
  cat .env
"
```

Anotar o valor de `WEBHOOK_SECRET` — será usado no GitHub.

- [ ] **Step 9: Fazer o primeiro deploy**

```bash
sudo -u deploy bash -c "
  cd /home/deploy/barbearia-chatbot
  docker compose up -d --build
"
```

Acompanhar os logs:
```bash
sudo -u deploy docker compose -f /home/deploy/barbearia-chatbot/docker-compose.yml logs -f
```

Esperado: Caddy obtém certificado SSL automaticamente (DNS já deve estar propagado).

---

## Task 10: Configurar GitHub Webhook

- [ ] **Step 1: Pegar o valor do WEBHOOK_SECRET da VM**

```bash
# Na VM
cat /home/deploy/barbearia-chatbot/.env
```

- [ ] **Step 2: Adicionar webhook no GitHub**

  No repositório → Settings → Webhooks → Add webhook:
  - **Payload URL:** `https://api.virtualbarber.shop/deploy`
  - **Content type:** `application/json`
  - **Secret:** valor do `WEBHOOK_SECRET` anotado acima
  - **Which events:** "Just the push event"
  - **Active:** marcado
  - Clique "Add webhook"

- [ ] **Step 3: Testar o webhook**

  Faça qualquer commit e push na branch `main`:
  ```bash
  git commit --allow-empty -m "test: verificar webhook de deploy"
  git push origin main
  ```

  No GitHub → Settings → Webhooks → clique no webhook → "Recent Deliveries" — deve aparecer um POST com status 200.

  Na VM, verificar logs:
  ```bash
  sudo -u deploy docker compose -f /home/deploy/barbearia-chatbot/docker-compose.yml logs webhook
  ```

---

## Task 11: Verificação Final

- [ ] **Step 1: Verificar frontend**

  Abrir `https://virtualbarber.shop` no browser — deve carregar o painel Next.js com HTTPS.

- [ ] **Step 2: Verificar backend**

  ```bash
  curl https://api.virtualbarber.shop/docs
  ```
  Esperado: HTML do Swagger UI do FastAPI.

- [ ] **Step 3: Verificar renovação automática do SSL**

  O Caddy renova automaticamente — sem ação necessária. Verificar validade do certificado:
  ```bash
  curl -vI https://virtualbarber.shop 2>&1 | grep -A2 "expire date"
  ```

- [ ] **Step 4: Commit de fechamento**

```bash
git add .
git commit -m "chore: finalizar configuração de deploy VPS GCP"
```

---

## Apêndice: Troca de Domínio no Futuro

Quando trocar `virtualbarber.shop` para outro domínio:

1. Atualizar DNS (registros A) no novo provedor
2. Editar `Caddyfile` (2 linhas — trocar `virtualbarber.shop`)
3. Editar `docker-compose.yml` — arg `NEXT_PUBLIC_API_URL`
4. Editar `backend/.env.production` — `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, `BACKEND_PUBLIC_BASE_URL`, `BOOKING_PUBLIC_BASE_URL`
5. Na VM: `cd /home/deploy/barbearia-chatbot && git pull && docker compose up -d --build`
6. Atualizar Payload URL do webhook no GitHub
