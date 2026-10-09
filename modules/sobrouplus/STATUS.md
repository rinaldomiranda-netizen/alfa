# Sobrou+ — status real (regra de verdade)

Estados usados: IMPLEMENTADO E VALIDADO · IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL · PARCIAL · PENDENTE · BLOQUEADO POR DEPENDÊNCIA.
Nesta revisão, "validado" para pagamentos significa coberto por 48 testes automatizados em banco temporário; nenhum pagamento real foi criado nem confirmado.

## 04/10/2026 — avaliações bilaterais e fidelidade

- Cliente e empresa podem avaliar a outra parte de 1 a 5 estrelas após pedido concluído, no máximo uma vez por pedido; comentários são opcionais.
- Nota média da empresa continua alimentando a vitrine. A reputação do cliente e as avaliações recebidas ficam no perfil/áreas autorizadas, sem publicação pública.
- O cliente ganha automaticamente 1 ponto por real em pedido concluído; o crédito é único e independente das estrelas. Pontos aparecem no perfil.
- Pontos nesta etapa não são dinheiro nem desconto; a conversão em benefício financeiro depende de definir quem financia o custo.
- Migração 13 cria tabelas restritas por pedido para avaliações de clientes e pontos de fidelidade; avaliações do cliente ficam privadas para a empresa envolvida e plataforma autorizada.
- Validação final: compilação Python, sintaxe dos quatro scripts JavaScript e 48 testes automatizados aprovados em banco temporário.

## 04/10/2026 — preparação para pagamentos online reais

- Backend estruturado para Mercado Pago Checkout Pro: criação idempotente de cobrança, referência exata ao pedido, consulta no servidor, confirmação por webhook assinado, cancelamento, estorno, parcelas e conciliação.
- Cartão, Pix e boleto ficam no checkout hospedado e dependem da disponibilidade da conta Mercado Pago. Dados de cartão não passam pelo Sobrou+.
- Pagamento real permanece desligado até informar credenciais separadas de sandbox/produção e uma URL HTTPS pública de webhook no ambiente do servidor.
- Tela administrativa de pagamentos lista pedido, cliente, valor, método, status, identificadores, datas e resumo higienizado da resposta; ações de cancelar e estornar chamam o provedor.
- Segredos são lidos do ambiente do servidor. O painel não os grava nem recebe access token. O navegador de retorno não aprova pagamentos.
- PagBank: adaptador ainda não implementado; a estrutura comum está pronta, mas usar PagBank exigirá escrever e validar o adaptador específico. Esta versão não deve ser anunciada como integração PagBank pronta.
- Verificações finais: compilação Python, sintaxe dos quatro scripts JavaScript e 48 testes passaram em banco descartável; transporte de teste, sem cobrança ao vivo.
- O código está no módulo local Desktop\\ALFA\\modules\\sobrouplus; ainda não está publicado no serviço hospedado. A ativação online também depende de implantação, credenciais e configuração do webhook no provedor.

## 04/10/2026 — revisão anterior das integrações e fluxo de demonstração

- Mercado Pago: cada tentativa Pix/cartão agora grava seu identificador antes de chamar o provedor e repete a mesma chave de idempotência em caso de timeout, evitando outra cobrança ao repetir a chamada.
- Webhook de pagamento: assinatura secreta passou a ser obrigatória; sem segredo ou com assinatura inválida o sistema não libera o pedido.
- Cliente → empresa → retirada → avaliação: a avaliação já estava ligada ao pedido concluído. O cliente avalia após concluir; a empresa lê e responde no painel, e a nota alimenta a vitrine.
- Banco separado de demonstração ganhou fluxos fictícios: pedido #1001 concluído por retirada e avaliado com 5 estrelas; pedido #1002 pago e enviado à fila do Dispatch. O pedido #1000 existente permanece como pedido pago. Pagamentos são exclusivamente de teste.
- APIs públicas local (8096) e publicada responderam HTTP 200 em saúde, configuração e vitrine (5 ofertas). Pedido sem autenticação respondeu HTTP 401, conforme esperado.
- Atalho do Laboratório corrigido para validar o segredo atual do banco de demonstração. Painel da empresa, app do cliente e app do entregador foram abertos no navegador local; configurações, pedido, avaliação e Dispatch conferidos visualmente.
- Suíte atual: 46 testes passaram, incluindo repetição idempotente do Pix e rejeição de webhook sem segredo.
- Alterações estão no módulo local do ALFA. A versão hospedada respondeu, mas não recebeu este código; precisa ser atualizada para levar as correções à internet.

## 03/10/2026 — Claude — versão 0.3.0 (no ar em https://rmd-atendimento-web-production.up.railway.app/sobrou/)

"Validado" = 44 testes automáticos passando + telas conferidas no navegador (computador e tamanho de celular).

| Parte | Estado |
|---|---|
| Acesso do Criador só com a senha (padrão 1234, sem troca obrigatória; aviso vermelho até trocar; troca em Configurações) | IMPLEMENTADO E VALIDADO |
| Verificação em 2 etapas (código do Google/Microsoft Authenticator), código não pode ser reusado | IMPLEMENTADO E VALIDADO |
| Aparelhos conectados + "sair de todos os outros aparelhos" | IMPLEMENTADO E VALIDADO |
| Link de acesso: o Criador/empresa cadastra a pessoa → o sistema gera o link (7 dias, uso único) → a pessoa cria a própria senha e cai na área dela. Botões copiar / WhatsApp / e-mail | IMPLEMENTADO E VALIDADO |
| Modo teste do Criador: abrir qualquer tela (cliente, empresa, balcão, entregador, financeiro, logística, instituição) numa Loja Teste, com "Voltar ao Criador" | IMPLEMENTADO E VALIDADO |
| Configurações (aparência, plataforma, empresa, dados do Pix para repasse, conta, segurança, avisos) | IMPLEMENTADO E VALIDADO |
| Atualização automática (o app confere a versão ao abrir/voltar e recarrega sozinho) | IMPLEMENTADO E VALIDADO |
| Financeiro detalhado (Criador: receita Sobrou+, taxas, mensalidades, GMV, ticket médio, a repassar, estornos, por empresa com Pix; Empresa: vendas, entregas, retiradas, a receber) + gráfico + período | IMPLEMENTADO E VALIDADO (sobre pagamentos de teste) |
| Relatórios para Excel (pedidos, ofertas, doações, repasses, avaliações) | IMPLEMENTADO E VALIDADO |
| Avaliações com estrelas (cliente avalia pedido concluído; loja responde; nota na vitrine) | IMPLEMENTADO E VALIDADO |
| Planos e mensalidades (Essencial/Profissional/Destaque; taxa, limite de ofertas, destaque; fatura mensal) | IMPLEMENTADO E VALIDADO (cobrança automática da mensalidade: PENDENTE — marcada paga à mão) |
| Esqueci minha senha (código por e-mail) | IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL (precisa ligar um e-mail SMTP em Integrações) |
| Backup automático diário (guarda 14) + baixar backup | IMPLEMENTADO E VALIDADO |
| Termos de Uso, Política de Privacidade, aceite obrigatório, baixar meus dados, excluir conta (LGPD) | IMPLEMENTADO E VALIDADO (texto jurídico: revisar com advogado) |
| App instalável (PWA) + aviso no celular com o app fechado (Web Push) | IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL (testar num celular) |
| Pix/cartão Mercado Pago, WhatsApp oficial | IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL — BLOQUEADO POR DEPENDÊNCIA (credenciais das contas) |
| Mapa pelas ruas (OSRM) e busca de endereço (Nominatim) | IMPLEMENTADO E VALIDADO (online) |

## 02/10/2026 — Claude — versão 0.1.0 (sistema novo, independente)

Base: cópia identificada dos padrões testados do RMD Atendimento (segurança/senhas/sessões, banco SQLite com migrações,
permissões por papel, servidor web sem dependências). O RMD Delivery original NÃO foi tocado nem copiado (não tem backend real).
Banco próprio: `SobrouPlus\data\sobrou.db` (real) e `SobrouPlus\data\demo\` (demonstração). Não mistura com nenhum outro sistema.

| Parte (combinado §27) | Estado |
|---|---|
| Autenticação (senha forte, bloqueio por tentativas, sessão em cookie seguro, troca obrigatória da senha inicial) | IMPLEMENTADO E VALIDADO |
| RBAC — 9 papéis (admin/operador Sobrou+, admin/operador da empresa, financeiro, logística, entregador, cliente, instituição) | IMPLEMENTADO E VALIDADO |
| Multiempresa: empresa A não vê/edita nada da empresa B (oferta, pedido, retirada, financeiro, auditoria) | IMPLEMENTADO E VALIDADO |
| Cadastro de parceiro com aprovação da equipe Sobrou+ antes de publicar | IMPLEMENTADO E VALIDADO |
| Unidades (endereço, instruções de retirada, localização pelo aparelho) | IMPLEMENTADO E VALIDADO |
| Oferta antissobra: produto, cesta surpresa (faixa de valor), kit; janela de venda e de retirada; validade; prioridade | IMPLEMENTADO E VALIDADO |
| Upload real de foto (comprimida no aparelho 1280 px + miniatura 400 px; só JPG/PNG/WebP; várias fotos) | IMPLEMENTADO E VALIDADO |
| Estoque real (disponível, reservado, vendido, sobra/expirado, doado; nunca vende acima; histórico de movimentos) | IMPLEMENTADO E VALIDADO |
| Preço inteligente (fixo, progressivo por tempo, por estoque; piso do parceiro; histórico de toda mudança) | IMPLEMENTADO E VALIDADO |
| Checkout (valida estoque, limite por cliente, retirada/entrega, raio, total, economia) e reserva de 15 min | IMPLEMENTADO E VALIDADO |
| Pedidos com os 18 estados e histórico completo | IMPLEMENTADO E VALIDADO |
| Retirada com PIN + QR, sem duplicidade; "não retirado" automático após a janela | IMPLEMENTADO E VALIDADO |
| Pagamento | PARCIAL — só MODO TESTE (aprova sem cobrar). Pix/cartão reais: BLOQUEADO POR DEPENDÊNCIA (conta no meio de pagamento) |
| Webhooks de pagamento | BLOQUEADO POR DEPENDÊNCIA (mesma conta + endereço público HTTPS) |
| Dispatch (distância, GPS recente, capacidade, entregador próprio × rede, urgência da janela, prazo de aceite, recusa → próximo, designação manual) | IMPLEMENTADO E VALIDADO (sem agrupamento de rotas: PENDENTE) |
| App do entregador (online, aceitar/recusar, coleta, entrega com código do cliente, ganhos) | IMPLEMENTADO E VALIDADO |
| GPS / telemetria do entregador (GPS do celular pelo navegador) | IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL (celular fora deste computador exige HTTPS) |
| Mapa com ruas / busca de endereço | BLOQUEADO POR DEPENDÊNCIA (provedor de mapas). Hoje: distância em linha reta + botão "abrir rota" no Google Maps |
| Notificações dentro do sistema (sino) | IMPLEMENTADO E VALIDADO |
| WhatsApp transacional / push no celular | BLOQUEADO POR DEPENDÊNCIA (conta Meta WhatsApp Business) |
| Financeiro (GMV, taxa Sobrou+ por empresa, economia do cliente, receita recuperada, entrega, a repassar) | IMPLEMENTADO E VALIDADO (sobre pagamentos de teste) |
| Repasses (calcular por período sem duplicar, marcar pago com comprovante) | IMPLEMENTADO E VALIDADO (transferência bancária em si é feita fora do sistema) |
| Conciliação (pagamento × pedido × repasse, lista divergências) | IMPLEMENTADO E VALIDADO (extrato bancário real: BLOQUEADO POR DEPENDÊNCIA) |
| Doação real: instituição autorizada → aceite → coleta (nome de quem retirou) → destinação (pessoas beneficiadas), quem/quando em cada passo | IMPLEMENTADO E VALIDADO |
| Impacto (kg vendidos/doados, unidades, economia, receita, instituições, pessoas) — só conta o confirmado | IMPLEMENTADO E VALIDADO (gráficos/mapa: PENDENTE) |
| Auditoria (preço, estoque, pedido, cancelamento, oferta, repasse, doação, usuário, configuração) | IMPLEMENTADO E VALIDADO |
| Logs de erro (tela Sistema) | IMPLEMENTADO E VALIDADO |
| Tema claro/médio/escuro, nome da empresa no topo, cabeçalho profissional | IMPLEMENTADO E VALIDADO |
| Logomarca oficial | PENDENTE — falta o arquivo SobrouPlus_Logo_Aprovada.png (copiar como `web\static\img\logo.png`). Não foi criado logo substituto. |
| Fotos reais nas ofertas de demonstração | PENDENTE — a demonstração mostra "foto real pendente" (nunca desenho) |
| Arquivos de referência V1/V2 do ChatGPT | PENDENTE (pedido no PEDIDO_ATUAL_CHATGPT) |
| Publicação na internet (HTTPS) | PENDENTE — roda neste computador e na rede Wi-Fi local |

Como usar: `Sobrou+ (real).bat` (banco real, vazio; primeiro acesso do dono com a senha inicial padrão e troca obrigatória)
ou `Sobrou+ (demonstracao).bat` (dados de exemplo, escolhe o perfil). Testes: `Testar Sobrou+.bat`.

## Histórico
## 02/10/2026 — Claude — passo 1 do combinado: localizar a base real do RMD Delivery

Encontrado:
- `Desktop\ALFA\modules\delivery\index.html` (RMD Delivery — Plataforma de Entregas): **protótipo em HTML** (167 KB),
  dados no navegador (`localStorage`, 47 usos) e sincronização de um "estado" único em `/api/conis/state` e `/api/sandbox-config`.
- `Desktop\ALFA\modules\delivery\RMD_Delivery_Platform.html` e `modules\rmd-delivery\index.html`: telas HTML.
- `Desktop\CONIS_PUBLICAR\api`: Azure Function única (`conis/index.js`) do cliente CONIS/Ohane — infraestrutura de
  cliente, fora do ALFA. Não reutilizar.

NÃO encontrado: banco próprio do RMD Delivery, tabelas, migrations, Supabase, autenticação, RBAC, storage, webhooks.

Conclusão: o "backend do RMD Delivery" **não existe como sistema real**. Pela regra 2/29 do combinado, nada foi
copiado nem declarado como copiado. O RMD Delivery original não foi tocado.

Arquivos de referência citados no combinado (SobrouPlus_Logo_Aprovada.png, SobrouPlus_V2_Identidade_Aprovada.html,
SobrouPlus_Sistema_V1_RMD_Base.html): **não encontrados** nas pastas ligadas a esta sessão.
Encontrado só: `Desktop\SobrouPlus_WhatsApp\` (SobrouPlus_Computador.html, SobrouPlus_Celular.html — protótipos visuais).

## 04/10/2026 — rotas, despacho, ocorrências e análise de marketing

- O mapa do painel e do entregador agora desenha somente a geometria viária retornada pelo roteador. Se o OSRM estiver indisponível, a tela avisa e não desenha uma linha reta como se fosse rota; estimativas de distância continuam identificadas como estimativa.
- Despacho sequencial com 60 segundos por oferta, candidatos próximos ordenados usando rotas viárias em cache para até cinco candidatos; fim da fila muda para “falhou”, avisa a empresa e permite reiniciar a busca sem selecionar um entregador.
- Entregador tem links para Google Maps e Waze, alerta sonoro ativável, e registro autenticado de ocorrência (recusa do cliente, ausência ou não pagamento), que interrompe a corrida e avisa cliente e empresa.
- Cliente recebe o aviso “Aguardando entregador” e notificações de estado; painel de Dispatch atualiza automaticamente e pode emitir alerta sonoro após ativação.
- Migrações 14 e 15 criam eventos pseudônimos de navegação e ocorrências de entrega. O painel “Análise e marketing” é exclusivo da plataforma; mostra acessos, visitas por empresa, ofertas, checkout, pedidos, conversão, desistências e recomendações baseadas nos dados disponíveis. Retenção analítica: 90 dias; não registra IP, nome, e-mail ou texto digitado.
- Os números analíticos começam na publicação desta versão; não há histórico importado nem dados fictícios.
- Pagamento presencial no app do entregador não foi ativado. A tentativa de separar pagamento pendente do fluxo de pedido foi rejeitada pelo revisor automático por risco de o sistema interpretar a aceitação da loja como pagamento confirmado; a implementação parcial foi removida. A confirmação presencial precisa de desenho seguro separado antes de ser adicionada.
- Verificação: compilação Python e sintaxe dos três JavaScripts passaram; relatório de marketing/telemetria e registro de ocorrência foram exercitados em banco temporário. Na suíte completa, 47/48 testes passaram e houve erro em `test_avaliacao_bilateral_e_pontos_unicos`; esse teste e a classe de avaliações passaram quando executados isoladamente. Resultado da suíte completa não fica marcado como totalmente aprovado.
- Alterações permanecem no módulo local Desktop\\ALFA\\modules\\sobrouplus; não foram publicadas nem acionaram cobrança/entrega reais.


## 04/10/2026 — segurança, liberação de recursos e privacidade operacional

- Migração 16 adiciona liberação global e por empresa de módulos, com herança do padrão da plataforma e auditoria das alterações. A interface esconde recursos bloqueados e a API também recusa as operações; pedidos existentes continuam consultáveis pelo cliente.
- Migração 17 registra o custo de hash por usuário. Senhas novas e redefinidas usam PBKDF2-HMAC-SHA256 com 600.000 iterações; contas antigas continuam entrando com o custo registrado e migram para o custo atual após autenticação correta.
- Administrador Sobrou+ e administrador de empresa precisam cadastrar TOTP antes de usar as áreas administrativas. Instalação nova recebe senha inicial aleatória, exibida uma única vez no terminal e com troca obrigatória; senha padrão antiga exige troca.
- Servidor configurado como público recusa inicialização sem a indicação explícita de HTTPS. Novas variáveis documentadas em .env.example.
- GPS: posição atual é usada para despacho enquanto entregador está disponível e para acompanhar uma entrega ativa. O sistema deixa de gravar novas trilhas de posição; trilhas antigas daquele entregador são apagadas no próximo envio de posição ou quando fica offline. Posição atual é limpa ao ficar offline sem corrida ativa e ao encerrar a última corrida estando offline.
- Análise de visitas e conversão já existente usa identificador pseudônimo, sem IP, nome, e-mail ou conteúdo livre, e retém eventos por até 90 dias. A liberação gradual por empresa usa os recursos globais/individuais já disponíveis.
- Validação: 48 testes automatizados aprovados em banco temporário; compilação Python e sintaxe dos JavaScript aprovadas. Avisos ResourceWarning foram emitidos pelos testes HTTP que exercitam respostas 4xx esperadas.
- Estado: alterações locais no módulo ALFA\\modules\\sobrouplus; não publicado. Pagamentos reais ainda dependem de credenciais do gateway, webhook HTTPS e implantação; adaptador PagBank continua pendente.
