# Checklist manual do modulo de pagamentos

Use este checklist em ambiente local ou staging. Nao use credenciais reais em testes locais compartilhados e nunca cole tokens em issues, prints ou logs.

## Preparacao

- [ ] Confirmar `APP_ENV=development` local ou `APP_ENV=staging` em homologacao.
- [ ] Confirmar `ENCRYPTION_KEY` configurada com valor de teste.
- [ ] Confirmar `FRONTEND_URL` e `BACKEND_URL` apontando para o ambiente testado.
- [ ] Confirmar `MERCADOPAGO_CLIENT_ID`, `MERCADOPAGO_CLIENT_SECRET`, `MERCADOPAGO_REDIRECT_URI` e `MERCADOPAGO_WEBHOOK_SECRET` configurados apenas em staging/producao.
- [ ] Confirmar que credenciais PicPay por estabelecimento foram cadastradas pelo ADM, criptografadas, e nao no `.env`.
- [ ] Confirmar que o banco usado no teste nao contem dados reais de clientes.

## OAuth Mercado Pago

- [ ] Entrar como estabelecimento A e abrir `Painel > Pagamentos`.
- [ ] Clicar em `Conectar Mercado Pago`.
- [ ] Verificar redirecionamento para o Mercado Pago com `state` na URL.
- [ ] Autorizar no ambiente sandbox/teste.
- [ ] Verificar retorno para `/painel/pagamentos?status=connected`.
- [ ] Verificar que o painel mostra somente status conectado, conta mascarada e datas.
- [ ] Reutilizar a mesma URL de callback e confirmar falha segura (`status=error`).
- [ ] Testar callback com `state` alterado e confirmar falha segura.
- [ ] Conferir no banco que `access_token_encrypted` e `refresh_token_encrypted` nao contem token puro.

## Multiestabelecimento

- [ ] Conectar Mercado Pago no estabelecimento A.
- [ ] Conectar Mercado Pago no estabelecimento B com outra conta sandbox.
- [ ] Criar pagamento no estabelecimento A e confirmar que o token usado pertence a A.
- [ ] Criar pagamento no estabelecimento B e confirmar que o token usado pertence a B.
- [ ] Tentar acessar status, pagamentos e agendamentos de B usando sessao/header de A e confirmar bloqueio ou lista vazia.
- [ ] Verificar que uma conta Mercado Pago ja vinculada nao pode ser conectada em outro estabelecimento.
- [ ] Para PicPay, cadastrar credenciais distintas por estabelecimento no ADM e confirmar que o provider padrao de A nao afeta B.

## Checkout

- [ ] Ativar `Pagamento obrigatorio para confirmar agendamento`.
- [ ] Configurar bloqueio entre 5 e 60 minutos.
- [ ] Criar agendamento publico para servico com preco valido.
- [ ] Verificar que o agendamento nasce como `pending_payment`.
- [ ] Verificar que o pagamento nasce como `pending`.
- [ ] Verificar que o frontend recebe apenas `checkout_url`, `appointment_id`, `payment_id` e `expires_at`.
- [ ] Confirmar que `access_token`, `refresh_token`, `client_secret` e webhook secret nao aparecem no response.
- [ ] Tentar checkout sem provider conectado e confirmar mensagem amigavel.
- [ ] Tentar usar servico de outro estabelecimento e confirmar erro.
- [ ] Tentar usar profissional de outro estabelecimento e confirmar erro.
- [ ] Confirmar que o horario fica bloqueado enquanto `pending_payment` ainda nao expirou.

## Webhook Mercado Pago

- [ ] Enviar webhook com assinatura invalida e confirmar `403`.
- [ ] Confirmar que webhook invalido nao muda pagamento nem agendamento.
- [ ] Enviar webhook valido de pagamento aprovado.
- [ ] Confirmar que o backend consulta o Mercado Pago antes de aprovar.
- [ ] Confirmar que amount, `external_reference` e metadata batem com o payment local.
- [ ] Verificar que pagamento aprovado vira `approved`.
- [ ] Verificar que agendamento pago vira `confirmado` e `payment_status=approved`.
- [ ] Reenviar o mesmo evento e confirmar resposta `ignored` por idempotencia.
- [ ] Enviar pagamento recusado/cancelado e confirmar que o agendamento nao fica confirmado.
- [ ] Enviar amount divergente e confirmar que nao confirma.
- [ ] Enviar metadata divergente e confirmar que nao confirma.
- [ ] Em production/staging, remover `MERCADOPAGO_WEBHOOK_SECRET` e confirmar que webhook e bloqueado.

## Webhook PicPay

- [ ] Cadastrar `x-picpay-token` e `x-seller-token` de teste pelo ADM.
- [ ] Definir PicPay como provider padrao do estabelecimento.
- [ ] Criar checkout PicPay e confirmar `provider=picpay` no payment.
- [ ] Enviar callback com `Authorization`/`x-seller-token` invalido e confirmar `403`.
- [ ] Enviar callback valido e confirmar que o backend consulta PicPay antes de aprovar.
- [ ] Reenviar o mesmo callback e confirmar idempotencia.
- [ ] Confirmar que callback PicPay de A nao confirma pagamento de B.

## Expiracao

- [ ] Criar agendamento `pending_payment` com `expires_at` vencido.
- [ ] Executar a rotina `expire_pending_appointments()`.
- [ ] Confirmar que o agendamento vira `expired`.
- [ ] Confirmar que o payment pendente vira `expired`.
- [ ] Confirmar que o horario expirado volta a aparecer como disponivel.
- [ ] Confirmar que agendamento ja pago nao expira.
- [ ] Confirmar que agendamento confirmado permanece bloqueando o horario.

## Seguranca e observabilidade

- [ ] Conferir responses do painel estabelecimento e ADM: nenhum token ou segredo deve aparecer.
- [ ] Conferir logs do backend durante connect, checkout, refresh e webhook: nenhum token puro deve aparecer.
- [ ] Conferir console do navegador: nenhum token ou segredo deve aparecer.
- [ ] Conferir que `.env` real nao esta versionado.
- [ ] Conferir que `.env.example` nao contem valores reais.
- [ ] Conferir que falhas de credencial ausente geram erro claro e sem segredo.

## Regressao antes de deploy

- [ ] Rodar testes automatizados do backend.
- [ ] Rodar typecheck/build do frontend.
- [ ] Testar manualmente Mercado Pago sandbox.
- [ ] Testar manualmente PicPay em ambiente de teste quando credenciais estiverem disponiveis.
- [ ] Conferir no banco que `payments.establishment_id`, `payment_accounts.establishment_id` e `appointments.estabelecimento_id` estao corretos.
