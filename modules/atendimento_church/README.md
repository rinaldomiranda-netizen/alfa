# RMD Atendimento Church — módulo ALPHA

Central de atendimento multicanal (WhatsApp, site, telefone, presencial) adaptada para igrejas: conversas, nomes (membros/congregados/visitantes), filas e equipes, solicitações, serviços, fluxos automáticos, agenda, alertas, relatórios, usuários e permissões, backup e configurações.

É um módulo irmão do RMD Atendimento original (`modules/atendimento`), mas com um domínio diferente: o original conduz uma entrevista de voz presencial usando o motor de `core/atendimento.py`; o Atendimento Church é uma central de atendimento humano, com equipe respondendo em vários canais — por isso tem seu próprio contrato aqui dentro, sem depender de `core.atendimento`.

## Estrutura

- `store.py` — persistência na beta-cloud (Supabase), tabelas `church_conversations` e `church_config` (documentos jsonb, isolados por `igreja_id`). Também gera o pacote de backup.
- `modulo.py` — fachada (`AtendimentoChurchModule`) usada pelo Alpha Core, no mesmo espírito de `modules/atendimento/modulo.py`.
- `service.py` — orquestra a fachada exigindo sempre `igreja_id` (multi-tenant, uma igreja nunca vê dado de outra) e cuida do envio/registro de mensagens do WhatsApp.
- `whatsapp.py` — integração opcional com o WhatsApp Business Platform (Meta Cloud API): confere o webhook, entende as mensagens recebidas e envia mensagens de verdade quando configurado (veja "WhatsApp de verdade" abaixo).
- `ui.py` — painel web (WSGI puro, sem framework): serve a tela (`webapp.html`) e os endpoints JSON (veja "Endereços da API" abaixo).
- `webapp.html` — a tela em si (a mesma interface já validada com o Rinaldo), adaptada para falar com o backend Python por HTTP em vez do armazenamento do Artifact.
- `launcher.py` — entrada simples para abrir o painel dentro do ALPHA.
- `test_church.py` — testes automatizados (loja, fachada, serviço, WhatsApp e app web — 56 testes).

## Nuvem (beta-cloud)

O módulo funciona sem nenhuma configuração — só que "offline": os dados ficam só na memória da página aberta, sem sincronizar entre aparelhos, e o indicador do cabeçalho mostra "Modo demonstração".

Para sincronizar de verdade entre aparelhos/congregações, defina no `.env` do ALFA:

```
BETA_CLOUD_PROJECT_URL=https://cxzzutbijljjteapowuv.supabase.co   # já usado pelo ALFA
BETA_CLOUD_SERVICE_ROLE_KEY=                                       # pegue no painel do Supabase (Project Settings > API > service_role)
```

A chave `service_role` é secreta e só deve existir no seu `.env` local — nunca em código, commit ou conversa. Ela nunca é enviada ao navegador: só o backend Python deste módulo a usa, e as tabelas `church_*` têm RLS ligado sem nenhuma policy pública, então sem essa chave ninguém (nem o próprio Supabase por engano) consegue ler ou gravar nelas.

## Várias igrejas com o mesmo módulo (multi-tenant)

Cada igreja é identificada por um `igreja_id`. Para atender mais de uma igreja com o mesmo módulo, abra a tela com `?igreja=<algum-id>` na URL, por exemplo `/?igreja=comunidade-vida-nova`. A própria tela guarda esse identificador e passa em todas as chamadas à API — uma igreja nunca vê os dados de outra. Sem esse parâmetro, tudo funciona normalmente como uma igreja só (`igreja_id="default"`), que é o caso mais comum e não exige nenhuma configuração extra.

Para atender várias igrejas com instâncias próprias em vez de uma só instância compartilhada, `criar_app_wsgi(service_factory=...)` aceita uma função `igreja_id -> AtendimentoChurchService` (veja `ui.py`).

## Chave de acesso opcional (CHURCH_API_TOKEN)

Por padrão, o módulo continua aberto como sempre foi — pensado para rodar por trás do próprio login do ALFA. Se este módulo for publicado sozinho, fora do ALFA, dá para travar as rotas de dados com uma chave simples:

```
CHURCH_API_TOKEN=escolha-uma-chave-qualquer-aqui
```

Com essa variável definida, a tela pede a chave na primeira vez que abre (fica guardada no navegador de quem digitou) e passa a enviá-la em toda chamada. Sem essa variável (o padrão), nada muda — ninguém precisa digitar chave nenhuma. `/`, `/index.html` e `/api/health` nunca pedem chave, mesmo com ela configurada.

## Tempo real

A tela usa uma conexão ao vivo (Server-Sent Events, `/api/stream`) para saber na hora quando uma conversa nova chega ou alguém muda uma configuração — sem ficar recarregando a cada poucos segundos. Se a hospedagem não permitir esse tipo de conexão de longa duração, a tela percebe sozinha e volta a perguntar de tempos em tempos, sem quebrar nada. Cada aba aberta usando o modo ao vivo ocupa uma conexão do servidor enquanto estiver aberta — tranquilo para o uso normal de uma equipe de atendimento (poucas pessoas simultâneas); para um volume muito maior, vale rever esse ponto.

## Backup de verdade

Na tela "Backup", o botão "Baixar backup agora" chama `/api/backup` e baixa um arquivo `.json` de verdade com todas as conversas e a configuração da igreja — só funciona com a nuvem conectada (modo online). A data do último backup baixado fica salva na configuração da igreja.

## Modo demonstração dos botões de teste

Os botões "Simular nova mensagem" e "Simular resposta da pessoa" (úteis para mostrar o sistema funcionando sem dados reais) só aparecem quando a tela é aberta com `?demo=1` na URL. No uso normal do dia a dia, esses botões ficam escondidos.

## Tipo de atendimento e telas de acompanhamento

Cada conversa pode ser marcada com um tipo (visitante, pedido de oração, aconselhamento pastoral, pedido de batismo, transferência de membresia, decisão por Cristo, dúvida geral ou outro) no painel de detalhes do atendimento. Duas telas novas usam essa marcação:

- **Acompanhamento de visitantes** — lista quem foi marcado como "Visitante" e mostra se o contato já foi feito, avisando quando passa de 2 dias sem retorno.
- **Pedidos de oração** — lista quem foi marcado como "Pedido de oração", para a equipe de intercessão acompanhar separadamente, marcando cada um como "orando" ou "atendido".

O atendimento também pode ser atribuído a uma pessoa específica da equipe (não só à fila/departamento), guardar o dia/horário desejado para um agendamento e, opcionalmente, a data de aniversário da pessoa (formato `DD/MM`) — que aparece no Dashboard, na semana do aniversário.

## Respostas rápidas configuráveis

Em "Respostas rápidas", no menu, dá para cadastrar e remover as mensagens prontas que aparecem como sugestão durante o atendimento (antes eram fixas no código).

## WhatsApp de verdade (opcional)

Por padrão, o WhatsApp continua funcionando como um canal registrado manualmente, como sempre foi. Para ligar o envio e recebimento de verdade pelo número oficial da igreja, é preciso ter uma conta própria no **Meta for Developers** com um número do **WhatsApp Business** verificado — isso você cria e configura por sua conta (envolve aceitar os termos e eventuais custos do Meta; este módulo não cria contas nem lida com pagamento nenhum). Com a conta pronta, defina no `.env`:

```
WHATSAPP_TOKEN=                              # token de acesso do app da Meta
WHATSAPP_PHONE_NUMBER_ID=                    # ID do número (painel da Meta)
WHATSAPP_VERIFY_TOKEN=escolha-uma-palavra    # você escolhe; só confirma o endereço do webhook
WHATSAPP_APP_SECRET=                         # opcional, camada extra de segurança
```

No painel da Meta (WhatsApp > Configuration > Webhook), cadastre:

- **URL de callback**: `https://SEU-DOMINIO/api/whatsapp/webhook?igreja=<id>` (a tela "WhatsApp" no menu mostra esse endereço já pronto para copiar)
- **Token de verificação**: o mesmo valor de `WHATSAPP_VERIFY_TOKEN`
- **Campo (fields) a assinar**: `messages`

Enquanto essas variáveis não estiverem definidas, nada muda — o indicador na tela "WhatsApp" continua mostrando "Não conectado" e o atendimento funciona normalmente pelos outros canais.

## Endereços da API

```
GET  /api/state             -> {"online": bool, "conversas": [...], "cfg": {...}, "zap": bool}
GET  /api/stream            -> a mesma coisa, em tempo real (Server-Sent Events)
POST /api/conversa          -> grava uma conversa (corpo = documento da conversa)
POST /api/cfg               -> grava a configuração geral (corpo = documento de config)
GET  /api/backup            -> baixa um .json com todas as conversas e a configuração
GET  /api/health            -> "ok" (health check de hospedagem)
GET  /api/whatsapp/webhook  -> confirmação do webhook para a Meta
POST /api/whatsapp/webhook  -> recebe mensagens do WhatsApp (chamado pela Meta)
POST /api/whatsapp/enviar   -> envia uma mensagem de verdade pelo WhatsApp
```

Todas (menos `/api/health` e o webhook do WhatsApp) aceitam `?igreja=<id>` para multi-tenant e, se `CHURCH_API_TOKEN` estiver configurado, exigem a chave em `X-Church-Token` (cabeçalho) ou `?token=...`. O webhook do WhatsApp fica de fora dessa exigência porque quem chama é a própria Meta — a verificação dele é o handshake de confirmação (GET) e, opcionalmente, a assinatura `X-Hub-Signature-256` (`WHATSAPP_APP_SECRET`).

## Como abrir

Dentro do ALFA, como qualquer outro módulo descoberto por manifesto (`skills/rmd-atendimento-church/manifest.json`). Em modo standalone, sirva o app WSGI de `ui.criar_app_wsgi()` com qualquer servidor WSGI (gunicorn, waitress etc.) e abra a raiz (`/`) no navegador.

## Testes

```
python -m unittest modules.atendimento_church.test_church -v
```
