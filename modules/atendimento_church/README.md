# RMD Atendimento Church — módulo ALPHA

Central de atendimento multicanal (WhatsApp, site, telefone, presencial) adaptada para igrejas: conversas, nomes (membros/congregados/visitantes), filas e equipes, solicitações, serviços, fluxos automáticos, agenda, alertas, relatórios, usuários e permissões, backup e configurações.

É um módulo irmão do RMD Atendimento original (`modules/atendimento`), mas com um domínio diferente: o original conduz uma entrevista de voz presencial usando o motor de `core/atendimento.py`; o Atendimento Church é uma central de atendimento humano, com equipe respondendo em vários canais — por isso tem seu próprio contrato aqui dentro, sem depender de `core.atendimento`.

## Estrutura

- `store.py` — persistência na beta-cloud (Supabase), tabelas `church_conversations` e `church_config` (documentos jsonb, isolados por `igreja_id`).
- `modulo.py` — fachada (`AtendimentoChurchModule`) usada pelo Alpha Core, no mesmo espírito de `modules/atendimento/modulo.py`.
- `service.py` — orquestra a fachada exigindo sempre `igreja_id` (multi-tenant, uma igreja nunca vê dado de outra).
- `ui.py` — painel web (WSGI puro, sem framework): serve a tela (`webapp.html`) e três endpoints JSON (`/api/state`, `/api/conversa`, `/api/cfg`) além de `/api/health`.
- `webapp.html` — a tela em si (a mesma interface já validada com o Rinaldo), adaptada para falar com o backend Python por HTTP em vez do armazenamento do Artifact.
- `launcher.py` — entrada simples para abrir o painel dentro do ALPHA.
- `test_church.py` — testes automatizados (loja, fachada, serviço e app web).

## Nuvem (beta-cloud)

O módulo funciona sem nenhuma configuração — só que "offline": os dados ficam só na memória da página aberta, sem sincronizar entre aparelhos, e o indicador do cabeçalho mostra "Modo demonstração".

Para sincronizar de verdade entre aparelhos/congregações, defina no `.env` do ALFA:

```
BETA_CLOUD_PROJECT_URL=https://cxzzutbijljjteapowuv.supabase.co   # já usado pelo ALFA
BETA_CLOUD_SERVICE_ROLE_KEY=                                       # pegue no painel do Supabase (Project Settings > API > service_role)
```

A chave `service_role` é secreta e só deve existir no seu `.env` local — nunca em código, commit ou conversa. Ela nunca é enviada ao navegador: só o backend Python deste módulo a usa, e as tabelas `church_*` têm RLS ligado sem nenhuma policy pública, então sem essa chave ninguém (nem o próprio Supabase por engano) consegue ler ou gravar nelas.

## Como abrir

Dentro do ALFA, como qualquer outro módulo descoberto por manifesto (`skills/rmd-atendimento-church/manifest.json`). Em modo standalone, sirva o app WSGI de `ui.criar_app_wsgi()` com qualquer servidor WSGI (gunicorn, waitress etc.) e abra a raiz (`/`) no navegador.

## Testes

```
python -m unittest modules.atendimento_church.test_church -v
```
