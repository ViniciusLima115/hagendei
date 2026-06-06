# Payments implementation

Este documento descreve como configurar, testar e manter o modulo de pagamentos do SaaS multiestabelecimento da HTECH.

## Visao geral

O sistema e multiestabelecimento. Cada estabelecimento possui seus proprios agendamentos, servicos, profissionais, pagamentos e integracoes de pagamento vinculados ao `establishment_id`.

No modelo atual, cada estabelecimento conecta sua propria conta Mercado Pago pelo fluxo OAuth. O cliente do estabelecimento nao informa login, senha, `access_token` ou `client_secret`: ele apenas autoriza a aplicacao no Mercado Pago.

Os tokens OAuth retornados pelo Mercado Pago sao salvos criptografados no banco, na tabela de contas/integracoes de pagamento. A API nunca retorna `access_token` ou `refresh_token` para o frontend.

O dinheiro cai na conta Mercado Pago conectada pelo estabelecimento. A plataforma apenas cria o checkout usando o token daquele estabelecimento e confirma o agendamento depois da aprovacao do pagamento.

## Variaveis de ambiente

Configure estas variaveis no backend. Nunca coloque segredos reais no repositorio.

| Variavel | Obrigatoria em producao | Descricao |
| --- | --- | --- |
| `ENCRYPTION_KEY` | Sim | Chave usada para criptografar tokens sensiveis no banco. |
| `MERCADOPAGO_CLIENT_ID` | Sim | Client ID da aplicacao OAuth cadastrada no Mercado Pago. |
| `MERCADOPAGO_CLIENT_SECRET` | Sim | Client Secret da aplicacao OAuth cadastrada no Mercado Pago. |
| `MERCADOPAGO_REDIRECT_URI` | Sim | URL de callback OAuth cadastrada no Mercado Pago. Exemplo: `https://api.seudominio.com/payments/mercadopago/callback`. |
| `MERCADOPAGO_WEBHOOK_SECRET` | Sim | Secret usado para validar assinatura/HMAC dos webhooks Mercado Pago. |
| `FRONTEND_URL` | Sim | URL publica do painel/frontend. Usada nos redirects depois do OAuth e nas URLs de retorno do checkout. |
| `BACKEND_URL` | Sim | URL publica da API. Usada para montar `notification_url` dos webhooks. Deve ser HTTPS em producao. |

Tambem existem variaveis auxiliares como `DATABASE_URL`, `APP_ENV`, `MERCADOPAGO_TIMEOUT_SECONDS`, `MERCADOPAGO_API_BASE`, `MERCADOPAGO_AUTH_BASE`, `PICPAY_API_BASE` e `PICPAY_TIMEOUT_SECONDS`. Consulte `backend/.env.example` para a lista operacional completa.

## Como gerar ENCRYPTION_KEY

Use uma chave Fernet:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Guarde essa chave com seguranca no provedor de variaveis de ambiente. Ela nao deve ser enviada por chat, commitada, impressa em logs ou compartilhada em tickets.

Importante: depois que tokens forem criptografados com uma `ENCRYPTION_KEY`, trocar essa chave sem migrar os tokens torna os tokens antigos ilegiveis. Para trocar a chave em producao, planeje uma migracao controlada ou force reconexao das contas.

## Fluxo OAuth Mercado Pago

1. O estabelecimento acessa `Painel > Pagamentos`.
2. O usuario clica em `Conectar Mercado Pago`.
3. O backend valida o usuario autenticado e identifica o `establishment_id` pelos claims/header da sessao.
4. O backend gera um `state` aleatorio e seguro.
5. O `state` e salvo com `establishment_id`, `user_id`, provider e expiracao de 15 minutos.
6. O backend retorna ou redireciona para a URL de autorizacao do Mercado Pago com `client_id`, `response_type=code`, `redirect_uri` e `state`.
7. O estabelecimento autoriza no Mercado Pago.
8. O Mercado Pago chama `MERCADOPAGO_REDIRECT_URI` com `code` e `state`.
9. O backend valida se o `state` existe, nao expirou e ainda nao foi consumido.
10. O backend troca o `code` por `access_token`, `refresh_token`, `public_key` e dados da conta.
11. Os tokens sao criptografados e salvos vinculados ao `establishment_id` do `state`.
12. O `state` e marcado como consumido para impedir reuso.
13. O usuario volta para `FRONTEND_URL/painel/pagamentos?status=connected`.

O callback nao deve confiar em `establishment_id` vindo do frontend. A vinculacao correta vem do `state` salvo no backend.

## Fluxo de checkout

1. O cliente escolhe estabelecimento, servico, profissional e horario.
2. O backend valida se o servico e o profissional pertencem ao mesmo estabelecimento.
3. Se pagamento antecipado for obrigatorio, o agendamento nasce com `status=pending_payment`.
4. O pagamento nasce com `status=pending`.
5. O horario fica bloqueado temporariamente ate `expires_at`.
6. O backend busca a integracao ativa do estabelecimento e do provider padrao.
7. O backend descriptografa o token apenas em memoria.
8. O backend cria o checkout/preference no provider de pagamento.
9. O frontend recebe somente `checkout_url`, `appointment_id`, `payment_id` e `expires_at`.
10. O cliente paga no checkout do provider.
11. O webhook informa o backend.
12. O backend consulta o provider antes de confiar no pagamento.
13. Se o pagamento estiver aprovado e bater com o registro local, o pagamento vira `approved`.
14. O agendamento vira `confirmed`/`confirmado`.

O agendamento nao deve ser confirmado pelo frontend antes da aprovacao real via webhook.

## Webhook Mercado Pago

Configure no painel Mercado Pago a URL publica:

```text
https://api.seudominio.com/webhooks/mercadopago
```

Em ambiente local, use um tunel HTTPS quando precisar testar webhook real.

Regras do webhook:

- Deve validar assinatura/HMAC usando `MERCADOPAGO_WEBHOOK_SECRET`.
- Em producao, webhook sem secret configurado deve ser rejeitado.
- Nao use `?token=` ou qualquer segredo por query param.
- O payload recebido nao deve ser confiado cegamente.
- Ao receber evento, o backend extrai o ID do pagamento.
- O backend localiza o `payment` e o `establishment_id`.
- O backend busca a integracao Mercado Pago daquele estabelecimento.
- O backend descriptografa o token apenas em memoria.
- O backend consulta o pagamento diretamente na API do Mercado Pago.
- O backend valida status, valor, `external_reference`, metadata e conta do provider.
- So depois disso atualiza `payments` e `appointments`.

Idempotencia:

- Cada evento processado deve ser registrado.
- Evento duplicado deve responder 200 e ser ignorado.
- Confirmacao de agendamento nao pode acontecer duas vezes.

## Expiracao de pagamentos pendentes

Quando um checkout e iniciado, o horario fica bloqueado enquanto o agendamento esta em `pending_payment`.

O tempo de bloqueio e definido por `checkout_hold_minutes` na conta de pagamento do estabelecimento. O valor permitido e de 5 a 60 minutos. O padrao e 10 minutos.

A rotina `expire_pending_appointments()` deve:

- Buscar agendamentos `pending_payment`.
- Filtrar `expires_at`/`payment_hold_expires_at` vencido.
- Ignorar agendamentos ja pagos.
- Marcar agendamento pendente como `expired`.
- Marcar pagamento pendente como `expired`.
- Liberar o horario para novos agendamentos.

Execucao recomendada:

- Cron job da infraestrutura.
- Worker.
- Endpoint interno protegido por token.
- Agendamento nativo do provedor de hospedagem.

Se houver disputa entre webhook aprovando pagamento e rotina expirando, a confirmacao validada pelo provider deve prevalecer.

## Painel

### Painel do estabelecimento

O cliente do sistema deve ver apenas informacoes operacionais:

- Status da integracao: conectado, desconectado, expirado ou erro.
- Data da ultima conexao.
- Recebimento ativo/inativo.
- Pix/cartao habilitados quando aplicavel.
- Botao para conectar/reconectar Mercado Pago.
- Botao para desconectar.
- Configuracao de pagamento obrigatorio.
- Tempo de bloqueio do horario.
- Tipo de cobranca: total ou sinal.
- Provider padrao quando houver mais de um provider disponivel.

### Painel ADM

A equipe HTECH pode acompanhar integracoes por estabelecimento:

- Nome e ID do estabelecimento.
- Provider.
- Status.
- Data de conexao.
- Ultima atualizacao.
- Ultimo erro.
- Quantidade de pagamentos aprovados/falhos.
- Auditoria de acoes administrativas.
- Acoes de desativar, solicitar reconexao e testar checkout em ambiente de teste.

### Nunca mostrar

Nunca mostrar no painel do estabelecimento, no ADM ou no console do navegador:

- `access_token`
- `refresh_token`
- `client_secret`
- `MERCADOPAGO_WEBHOOK_SECRET`
- `ENCRYPTION_KEY`
- Tokens PicPay individuais

## Seguranca

Regras obrigatorias:

- Nunca pedir senha do Mercado Pago ao cliente.
- Nunca mostrar token ao frontend.
- Nunca salvar token puro no banco.
- Nunca colocar token individual de estabelecimento no `.env`.
- Nunca validar webhook por query param.
- Nunca logar payload completo se ele puder conter dados sensiveis.
- Usar HTTPS em producao para frontend, backend, OAuth callback e webhooks.
- Validar `establishment_id` em todas as queries de pagamentos, agendamentos, servicos e integracoes.
- Descriptografar tokens apenas em memoria e pelo menor tempo possivel.
- Mascarar identificadores sensiveis em logs e respostas.

## PicPay

A arquitetura esta preparada para multiplos providers, com `provider=mercado_pago` e `provider=picpay` em contas e pagamentos.

O Mercado Pago continua sendo a prioridade atual. O PicPay esta preparado como provider futuro/alternativo. O modelo recomendado e manter credenciais individuais por estabelecimento criptografadas no banco, nunca no `.env`.

Para ativar PicPay em producao ainda e necessario:

- Validar o contrato vigente da API PicPay com a conta comercial da HTECH.
- Confirmar se o modelo final sera OAuth, subseller/split ou credencial manual por estabelecimento.
- Homologar criacao de checkout com credenciais de teste.
- Homologar consulta de status antes da confirmacao.
- Homologar webhook/callback com assinatura ou token do seller.
- Definir fluxo operacional no ADM para cadastrar ou reconectar credenciais.
- Liberar UI final para escolha de PicPay como provider padrao somente quando homologado.
- Rodar os testes automatizados e o checklist manual.

## Checklist de producao

Antes de deploy em producao:

- [ ] `ENCRYPTION_KEY` configurada e guardada com seguranca.
- [ ] `MERCADOPAGO_CLIENT_ID` configurado.
- [ ] `MERCADOPAGO_CLIENT_SECRET` configurado.
- [ ] `MERCADOPAGO_REDIRECT_URI` configurado e cadastrado no Mercado Pago.
- [ ] `MERCADOPAGO_WEBHOOK_SECRET` configurado.
- [ ] `FRONTEND_URL` apontando para o dominio publico correto.
- [ ] `BACKEND_URL` apontando para a API publica com HTTPS.
- [ ] Webhook cadastrado no painel Mercado Pago: `/webhooks/mercadopago`.
- [ ] OAuth Mercado Pago testado ponta a ponta.
- [ ] Checkout testado com pagamento aprovado.
- [ ] Webhook valido testado.
- [ ] Webhook invalido testado.
- [ ] Idempotencia testada com evento duplicado.
- [ ] Expiracao de `pending_payment` testada.
- [ ] Logs verificados para garantir ausencia de tokens puros.
- [ ] Painel estabelecimento validado sem segredos.
- [ ] Painel ADM validado sem segredos.
- [ ] `.env` real fora do versionamento.
- [ ] `.env.example` sem valores reais.

## Testes

Testes automatizados principais:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_payment_config.py tests\test_payment_crypto.py tests\test_payments_module.py
```

Suite completa do backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Typecheck do frontend:

```powershell
cd frontend
npx.cmd tsc --noEmit
```

Checklist manual complementar:

```text
docs/payment-test-checklist.md
```
