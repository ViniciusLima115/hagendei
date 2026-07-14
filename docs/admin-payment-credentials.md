# Credenciais administrativas de pagamento

## Objetivo
Permitir que um admin ou super_admin cadastre credenciais Mercado Pago manualmente para cada estabelecimento, sem pedir senha da conta Mercado Pago e sem expor segredos no frontend, logs ou respostas de API.

Esta integracao nao usa OAuth nesta etapa. O cadastro e manual e usa credenciais de API/integracao.

## Onde cadastrar
No painel administrativo, abra o perfil/detalhes do estabelecimento e acesse a secao `Pagamentos`, subsecao `Mercado Pago`.

Somente usuarios com papel `admin` ou `super_admin` podem acessar a tela e as rotas administrativas. Usuarios comuns do estabelecimento, funcionarios e clientes finais nao podem cadastrar, listar, validar ou desativar credenciais.

## Campos Mercado Pago
Campos aceitos:

- `environment`: `sandbox` ou `production`.
- `public_key`: chave publica. Pode ser obrigatoria quando o checkout/frontend precisar dela.
- `access_token`: obrigatorio para ativar a integracao.
- `client_id`: opcional, somente se o fluxo atual precisar.
- `client_secret`: opcional, somente se o fluxo atual realmente usar.
- `webhook_secret`: usado para validacao HMAC do webhook quando configurado.
- `notes`: observacoes internas opcionais.

Nunca solicitar:

- Login do Mercado Pago.
- Senha do Mercado Pago.
- Codigo 2FA.
- Senha pessoal do cliente.
- Dados completos de cartao.

## Armazenamento seguro
As credenciais sao enviadas ao backend por rotas administrativas `POST`, `PUT` ou `PATCH`. Em producao, as rotas sensiveis exigem HTTPS.

O backend monta um JSON interno com as credenciais preenchidas:

```json
{
  "public_key": "...",
  "access_token": "...",
  "client_id": "...",
  "client_secret": "...",
  "webhook_secret": "...",
  "notes": "..."
}
```

Esse JSON inteiro e criptografado com AES-256-GCM antes de salvar em `payment_integrations.credentials_encrypted`. Cada gravacao usa nonce aleatorio, autenticacao de integridade, AAD e identificador de chave para permitir rotacao.

Regras importantes:

- O banco nao deve receber `access_token`, `client_secret` ou `webhook_secret` em texto puro.
- As credenciais nao ficam no `.env`.
- O cofre de segredos fornece `ENCRYPTION_KEY`; `ENCRYPTION_KEYRING` pode manter chaves antigas durante uma rotacao controlada.
- `ENCRYPTION_KEY` nao deve ir para o banco, frontend, logs ou responses.
- Se `ENCRYPTION_KEY` for perdida ou alterada, as credenciais ja salvas podem ficar irrecuperaveis.
- Base64 nao e criptografia.
- Hash nao substitui criptografia, porque o backend precisa descriptografar em memoria para chamar o Mercado Pago.

## Retorno para o frontend
Depois de salvar, o frontend limpa os campos sensiveis e exibe apenas status e mascaras.

As APIs administrativas nunca retornam:

- `access_token` completo.
- `public_key` completa.
- `client_secret` completo.
- `webhook_secret` completo.
- `credentials_encrypted`.
- `ENCRYPTION_KEY`.

Campos retornados podem incluir:

- `provider`
- `environment`
- `status`
- `validation_status`
- `last_validated_at`
- `connected_at`
- `updated_at`
- `updated_by`
- `public_key_masked`
- `access_token_masked`
- `webhook_secret_masked`
- `has_client_id`
- `has_client_secret`

## Validar conexao
Use o botao `Validar conexao` no painel.

O backend:

1. Busca a integracao do estabelecimento.
2. Descriptografa as credenciais apenas em memoria.
3. Chama uma API segura do Mercado Pago para validar o `access_token`.
4. Nao cria pagamento real.
5. Atualiza `validation_status` e `last_validated_at`.
6. Somente uma integracao `active` e `valid` pode iniciar checkout.
7. Retorna apenas se a credencial e valida ou invalida, com mensagem segura.

## Desativar integracao
Use o botao `Desativar integracao`.

O backend marca a integracao como `inactive` ou `disconnected`, registra auditoria e nao apaga historico:

- Pagamentos antigos permanecem.
- Agendamentos antigos permanecem.
- Eventos de webhook antigos permanecem.
- As credenciais nao sao retornadas ao frontend.

## Atualizacao parcial e limpeza de campos
Atualizacoes parciais usam `PATCH`.

Se um campo sensivel vier vazio, o backend nao apaga automaticamente o valor existente. Para apagar um campo, use uma flag explicita, por exemplo:

```json
{
  "environment": "production",
  "clear_client_secret": true
}
```

Isso evita apagar credenciais por acidente.

## Checkout por estabelecimento
Quando um cliente final cria um agendamento com pagamento:

1. O backend identifica o `establishment_id` do agendamento.
2. Busca a integracao ativa:
   - `establishment_id = appointment.establishment_id`
   - `provider = mercado_pago`
   - `status = active`
3. Descriptografa as credenciais apenas em memoria.
4. Usa o `access_token` daquele estabelecimento.
5. Cria a preferencia/pagamento no Mercado Pago.
6. Cria registro em `pagamentos`.
7. Retorna ao frontend apenas `checkout_url`, `payment_id` e `status`.

Regra critica: pagamento do Estabelecimento A usa somente credenciais do Estabelecimento A. Pagamento do Estabelecimento B usa somente credenciais do Estabelecimento B.

A reserva e a preferencia expiram em no maximo cinco minutos. O backend envia a expiracao ao Mercado Pago e tambem encerra localmente a reserva; um pagamento aprovado tardiamente entra em revisao em vez de ocupar silenciosamente uma vaga ja liberada.

O registro de pagamento nunca salva `access_token`, `client_secret` ou `webhook_secret`.

## Webhook Mercado Pago
O webhook nao confia cegamente no payload recebido.

Fluxo:

1. Recebe notificacao do Mercado Pago.
2. Localiza o pagamento por `external_payment_id`, `external_reference` ou metadata.
3. Descobre o `establishment_id` a partir do pagamento local.
4. Busca a integracao Mercado Pago ativa daquele estabelecimento.
5. Exige e valida a assinatura oficial `x-signature`, incluindo `data.id`, `x-request-id` e timestamp. Eventos antigos ou repetidos sao rejeitados/idempotentes.
6. Descriptografa o `access_token` apenas em memoria.
7. Consulta o Mercado Pago para confirmar o status real.
8. Confirma o agendamento somente se:
   - status real for aprovado;
   - `amount` bater com o esperado;
   - `external_reference` e metadata baterem;
   - `payment_id`, `appointment_id` e `establishment_id` forem consistentes.
   - moeda e conta recebedora corresponderem a integracao esperada.
9. Se o evento for duplicado, ignora com idempotencia.

Nao usar `?token=` na URL do webhook e nao aceitar validacao por token em query param.

## Auditoria
Acoes administrativas gravam registros em `admin_audit_logs`.

Campos principais:

- `admin_user_id`
- `establishment_id`
- `action`
- `entity_type`
- `entity_id`
- `ip_address`
- `user_agent`
- `metadata`
- `created_at`

Acoes registradas:

- `payment_credentials_created`
- `payment_credentials_updated`
- `payment_credentials_validated`
- `payment_credentials_disabled`
- `payment_checkout_test_created`
- `payment_credentials_validation_failed`

Metadata pode conter provider, environment e status. Metadata nunca deve conter:

- `access_token`
- `client_secret`
- `webhook_secret`
- `credentials_encrypted`
- dados completos de cartao ou pagamento

## Nota futura: autenticacao forte de admin
Futuro: implementar autenticacao forte para administradores usando WebAuthn/FIDO2 com chave fisica. Nao usar pendrive comum com arquivo secreto como fator de autenticacao.

Abordagens recomendadas:

- WebAuthn/FIDO2.
- Security key fisica como YubiKey, Feitian ou similar.
- Passkey/hardware security key.
- Exigir segundo fator para entrar no painel ADM ou para acoes sensiveis, como alterar credenciais de pagamento.

Nao implementar autenticacao com "pendrive comum" lendo arquivo secreto, porque o arquivo pode ser copiado facilmente.

## Checklist de producao
- `APP_ENV=production`.
- `ENCRYPTION_KEY` de 32 bytes configurada e protegida; `PAYMENT_CREDENTIALS_PEPPER` deve ser independente.
- `JWT_SECRET` forte configurado.
- `DATABASE_URL` configurado.
- `FRONTEND_URL` e `BACKEND_URL` corretos.
- HTTPS ativo para frontend e backend.
- Rotas administrativas protegidas por token e papel `admin` ou `super_admin`.
- Nenhuma credencial enviada por GET, query param ou URL.
- Nenhuma credencial salva em `localStorage` ou `sessionStorage`.
- Nenhuma credencial descriptografada em response.
- Logs revisados para nao expor segredos.
- Webhook configurado sem `?token=`.
- `webhook_secret` configurado e igual ao segredo exibido pelo Mercado Pago para esse webhook.
- Teste de validacao feito em sandbox antes de production.
- Checkout de teste em production somente com confirmacao explicita.
- Backup seguro do banco e gestao segura da `ENCRYPTION_KEY`.
