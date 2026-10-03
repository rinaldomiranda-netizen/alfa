# RMD Atendimento — servidor web

Módulo oficial do ALFA. Detalhes completos em `modules/atendimento/README.md`.

## Rodar separado do ALFA

```
python atendimento_web/app.py                 # http://127.0.0.1:8080
python atendimento_web/app.py --porta 9000
```

Primeiro acesso: abra o endereço e use o código mostrado na janela do servidor.
Por padrão só este computador acessa. Para publicar na internet (necessário para receber
mensagens do WhatsApp), coloque HTTPS na frente (túnel ou servidor) e rode com `--host 0.0.0.0`.

## Endereços principais

- `/` — sistema (login)
- `/chat?e=<empresa>` — chat do site para visitantes
- `/recepcao` — recepção por roteiro (protocolo ALFA)
- `/webhooks/whatsapp` — endereço que a Meta chama
- `/api/v1/...` — API pública (chave em API & Webhooks)
- `/api/health` — saúde do sistema
