# Pagamentos online — Sobrou+

## Estado

A implementação inicial de gateway é o **Mercado Pago Checkout Pro**. O cliente paga no checkout hospedado pelo Mercado Pago; o Sobrou+ não recebe número de cartão, CVV nem CPF. A conta do gateway decide quais formas oferece. O Checkout Pro inclui cartão e pode oferecer Pix e boleto quando habilitados para a conta.

O pedido só passa a **Pago** após o backend consultar o pagamento no Mercado Pago, conferir a referência da tentativa, moeda BRL e valor exato. O retorno do navegador não aprova pedidos. O webhook exige HMAC e cada evento é deduplicado. O endpoint de consulta também reconcilia o gateway no servidor.

**PagBank ainda não tem adaptador implementado.** Não selecione um provedor inexistente nem copie as variáveis do Mercado Pago. A camada atual isola o fluxo e o modelo de dados do pagamento, mas ativar PagBank exigirá implementar e validar o adaptador oficial antes de usar credenciais.

Sem credenciais, HTTPS público e evento de webhook configurados, os pagamentos permanecem desligados. Não há cobrança fictícia nem aprovação de teste no app.

## Variáveis do servidor

Copie o modelo de `.env.example` para o mecanismo de ambiente do servidor. Não coloque o arquivo com valores reais no frontend, no repositório ou em logs. A aplicação precisa ser reiniciada após mudar o ambiente.

### Sandbox

1. Defina `SOBROU_PAYMENT_PROVIDER=mercadopago` e `SOBROU_PAYMENT_ENV=sandbox`.
2. Preencha `MERCADOPAGO_PUBLIC_KEY_SANDBOX` e `MERCADOPAGO_ACCESS_TOKEN_SANDBOX` com credenciais TEST- da mesma aplicação.
3. Configure `SOBROU_PAYMENT_WEBHOOK_URL` para uma URL HTTPS pública terminada em `/api/webhooks/mercadopago`.
4. Cadastre essa URL no painel de desenvolvedor do Mercado Pago, habilite notificações de pagamento e copie a assinatura secreta para `MERCADOPAGO_WEBHOOK_SECRET_SANDBOX`.
5. Use contas e cartões de teste do Mercado Pago. Nunca use dados de produção no sandbox.

### Produção

Use uma aplicação e credenciais de produção separadas: `SOBROU_PAYMENT_ENV=production`, `MERCADOPAGO_PUBLIC_KEY_PRODUCTION`, `MERCADOPAGO_ACCESS_TOKEN_PRODUCTION` e `MERCADOPAGO_WEBHOOK_SECRET_PRODUCTION`. Configure a URL HTTPS pública de produção em `SOBROU_PAYMENT_WEBHOOK_URL`. Credenciais TEST- são recusadas no ambiente de produção.

`SOBROU_PAYMENT_MAX_INSTALLMENTS` limita as parcelas apresentadas (1 a 24; padrão 12). O Mercado Pago pode limitar o número real por conta, bandeira e valor.

## Segurança e dados

- Nunca salvar PAN, CVV, trilha magnética, senha ou tokenização de cartão no Sobrou+.
- Access Token e assinatura do webhook são lidos somente das variáveis do processo servidor. A migração 12 remove a configuração antiga de Mercado Pago que podia conter segredos no SQLite.
- A Public Key não é secreta, mas só é apresentada na tela administrativa; o checkout hospedado não precisa dela no navegador.
- A tabela `pagamentos` guarda o pedido, moeda, valor, meio confirmado, status, identificadores do gateway/preferência, parcelas, datas e um resumo permitido da resposta. Não guarda a resposta integral do gateway.
- A tabela `eventos_pagamento` registra IDs de webhook por provedor/ambiente para impedir processamento duplicado.
- O endpoint `GET /api/pagamentos` exige permissão financeira e aplica escopo da empresa. Cancelamento e estorno são operações reais no provedor e registram o resultado/solicitação no backend.
- A tela do cliente consulta o pedido ao servidor depois do checkout; nunca confia em URL de sucesso para liberar estoque ou operação.

## Endpoints

- `POST /api/pedidos/{id}/pagar` com `{"meio":"checkout"}`: cria ou reutiliza a tentativa idempotente e devolve o link hospedado.
- `GET /api/pedidos/{id}/pagamento`: reconcilia no servidor e devolve o estado do pedido.
- `POST /api/webhooks/mercadopago`: valida assinatura, deduplica o evento e consulta `GET /v1/payments/{id}`.
- `GET /api/pagamentos`: listagem administrativa com pedido, cliente, empresa, valor, método, estado, gateway ID e resposta resumida.
- `POST /api/pagamentos/{id}/cancelar`: cancela cobrança pendente no Mercado Pago.
- `POST /api/pagamentos/{id}/estornar`: solicita estorno integral de pagamento aprovado.

A tela administrativa está em **Painel → Pagamentos**. O status “Estorno solicitado” só muda para “Estornado” quando o Mercado Pago confirma por consulta/webhook.

## Validação para ativar

Antes de liberar pagamentos reais: configure sandbox e webhook HTTPS, execute a suíte automática isolada, valide uma compra usando apenas credenciais e cartões de teste do provedor, confira webhook pendente/aprovado/recusado/cancelado/estornado, cancelamento e estorno. Depois migre para credenciais de produção. A aplicação hospedada só terá essas mudanças após um deploy do módulo.
