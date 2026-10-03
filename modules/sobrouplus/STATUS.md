# Sobrou+ — status real (regra de verdade)

Estados usados: IMPLEMENTADO E VALIDADO · IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL · PARCIAL · PENDENTE · BLOQUEADO POR DEPENDÊNCIA.
"Validado" aqui = coberto por teste automático que passou (`Testar Sobrou+.bat`, 21 testes) e conferido nas telas.
Nada disso foi usado ainda por loja/cliente real.

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
