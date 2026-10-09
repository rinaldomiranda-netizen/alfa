# SOBROU+ — COMBINADO GERAL PARA CLÁUDIO CODE
## Documento mestre de requisitos, decisões, adaptação e status
DATA: 02/10/2026
PROJETO: Sobrou+ — marketplace de excedentes alimentares + delivery + impacto social
(Texto enviado pelo Rinaldo no chat em 02/10/2026; guardado aqui sem alterações de conteúdo.)

## REGRA PRINCIPAL
CRIAR UM SISTEMA NOVO E INDEPENDENTE PARA O SOBROU+.
NÃO alterar, quebrar, sobrescrever, substituir ou modificar o RMD DELIVERY ORIGINAL.
A arquitetura, módulos, regras e infraestrutura do RMD DELIVERY devem ser reaproveitados somente como base funcional/estrutural quando estiverem realmente disponíveis e comprovados.
O sistema Sobrou+ deve nascer separado. Toda alteração feita para Sobrou+ deve ocorrer no novo projeto. O RMD Delivery original deve permanecer intacto.

## 1. OBJETIVO
Plataforma agregadora de restaurantes, lanchonetes, padarias, supermercados, hortifrutis, cafés, lojas de alimentos e outros estabelecimentos com excedentes próprios para consumo. Vender alimentos que ainda podem ser consumidos, mas poderiam virar desperdício, por preços reduzidos.
Ajudar a: recuperar valor para o estabelecimento; economia para o consumidor; reduzir desperdício; facilitar retirada e delivery; organizar excedentes; controlar estoque; controlar janela de validade/retirada; preço inteligente; cesta surpresa; produtos específicos; doação/destinação; medir impacto social.
NÃO é só um app de descontos: marketplace; gestão de excedentes; estoque; ofertas; preço; pedidos; checkout; retirada; delivery; Dispatch; empresas; unidades; clientes; entregadores; financeiro; taxas; repasses; conciliação; relatórios; instituições; doações; impacto social; segurança; auditoria.

## 2. ARQUITETURA
RMD DELIVERY ORIGINAL: permanece intacto; não alterar; não quebrar; não sobrescrever; não usar como ambiente de testes destrutivos.
SOBROU+: projeto independente; banco independente ou ambiente separado; backend, frontend e autenticação independentes; configurações próprias; identidade visual própria; regras específicas do ramo antissobra.
REAPROVEITAR DO RMD DELIVERY: empresas/tenants; unidades; clientes; pedidos; estados de pedidos; entregadores; Dispatch; distância; ETA; zonas; capacidade; fallback; financeiro; taxas; repasses; conciliação; relatórios; planos e assinaturas; configurações; isolamento por empresa; arquitetura multiempresa; estrutura de operação de delivery.
REGRA: copiar somente o que for localizado e comprovado. Não inventar backend. Não dizer que o banco real foi copiado se ele não for localizado. Não dizer que Supabase/API/migrations foram copiados sem localizar e validar.
ATÉ AGORA: o material do RMD Delivery localizado é uma implementação/protótipo HTML da arquitetura. Não foi localizado dump/migration real do banco. Portanto: não inventar banco, tabela, API, Supabase ou autenticação; localizar primeiro a infraestrutura real caso esteja disponível.

## 3. IDENTIDADE VISUAL APROVADA
MARCA OFICIAL: Sobrou+. Logomarca aprovada = a da arte de referência: "Sobrou" em verde; "+" em laranja; folhas verdes; curva/sorriso inferior em laranja/vermelho; moderna; food-tech.
SLOGAN: "Boa comida. Mais valor. Menos desperdício."
ARQUIVO DE REFERÊNCIA: SobrouPlus_Logo_Aprovada.png
NÃO substituir a marca por "S+" genérico, logotipo improvisado, logo textual simples ou outro símbolo sem aprovação.
Padrão visual: food-tech; profissional; moderno; premium; fotos reais de alimentos; app moderno; painel administrativo profissional; visual de empresa real; nada infantil; nada de cartoon como padrão.

## 4. CORES
Uma cor principal de marca, secundárias, alerta, oportunidade, contraste adequado, hierarquia visual. Verde = sustentabilidade, confiança, naturalidade, disponibilidade, impacto. Cores quentes = ofertas, oportunidade, promoção, urgência, desconto, expiração, CTA. Não usar somente verde e branco.
PALETA: #0A563A verde escuro (marca, sidebar, navegação); #1FA361 verde vivo (positivo, sucesso, disponível, confirmado); #F57A20 laranja (CTA, compra, oportunidade, ofertas); #E74A3B coral/vermelho (desconto forte, urgência, risco, expiração, estoque crítico); #FFC94A amarelo (destaque, avisos leves, promoções); #FFF9EF creme (fundo); branco (superfície, cards); azul só para status técnicos.
REGRA: não depender só de cor — combinar cor, texto, ícone e status.

## 5. MERCADO E REFERÊNCIAS
Too Good To Go (Surprise Bags, retirada em janela, proximidade, mapa); FoodHero (food rescue, destaque visual); Flashfood (ofertas específicas, múltiplas lojas, mapa, supermercado).
DIRETRIZ: combinar produto específico, cesta surpresa, mapa, retirada, delivery, logística, estoque, preço, impacto. Não copiar interface de ninguém.

## 6. MÓDULOS PRINCIPAIS
1 Central Sobrou+; 2 Empresas parceiras; 3 Unidades; 4 Ofertas antissobra; 5 Cesta surpresa; 6 Estoque; 7 Pedidos; 8 Checkout; 9 Pagamento; 10 Retirada; 11 Delivery; 12 Dispatch; 13 Entregadores; 14 Clientes; 15 Financeiro; 16 Repasses; 17 Conciliação; 18 Relatórios; 19 Doações; 20 Instituições; 21 Impacto; 22 Configurações; 23 App mobile; 24 Segurança; 25 Auditoria; 26 Notificações; 27 Integrações; 28 WhatsApp; 29 GPS; 30 Mapas.

## 7. EMPRESAS PARCEIRAS
Agregador. Empresas podem: criar cadastro; cadastrar unidades, produtos, excedentes e ofertas; definir quantidade, preço normal e preço Sobrou+; configurar janela; escolher retirada/delivery; acompanhar pedidos, vendas, repasses, impacto, estoque e desempenho.
Tipos: restaurante; lanchonete; padaria; mercado; supermercado; hortifruti; café; confeitaria; outras alimentícias.

## 8. OFERTA ANTISSOBRA
Campos mínimos: nome; descrição; categoria; foto; empresa; unidade; preço normal; preço Sobrou+; desconto; quantidade; vendida; restante; início; fim; janela de retirada; entrega; status; prioridade; regra de expiração.
Tipos: 1 Produto específico; 2 Cesta surpresa; 3 Kit de excedentes.
Exemplo: Marmita Executiva — normal R$ 24,90; Sobrou+ R$ 12,50; 50%; 8 unidades; retirada 18:30–20:00.

## 9. ESTOQUE
Controlar: disponível; reservada; vendida; restante; limite mínimo; limite crítico; expirado; destinado à doação. Atualizar em: reserva; pagamento; cancelamento; retirada; entrega; devolução; expiração; doação. Não permitir venda acima do estoque real.

## 10. PREÇO INTELIGENTE
Considerar: quantidade restante; tempo restante; proximidade da janela; demanda; velocidade de vendas; distância; custo de entrega; estratégia do parceiro. Possibilidades: fixo; manual; automático; progressivo; por faixa de horário; conforme estoque.
REGRA: nunca alterar preço automaticamente sem regra configurável, histórico, registro da alteração e controle do parceiro.

## 11. CESTA SURPRESA
Quantidade; preço; valor estimado; categoria; janela; limite de vendas; retirada; entrega. Composição pode ficar parcialmente desconhecida; a empresa define a regra. O consumidor vê: categoria; quantidade; faixa de valor; preço; janela; estabelecimento; retirada/entrega.

## 12. MARKETPLACE DO CONSUMIDOR
Localizar, pesquisar, filtrar; ver fotos, empresa, unidade, preço normal, preço Sobrou+, desconto, estoque, distância, horário, retirada, delivery; comprar; acompanhar pedido; confirmar recebimento; ver impacto e histórico.
Filtros: distância; categoria; preço; desconto; retirada; delivery; horário; disponibilidade; produto; empresa.

## 13. EXPERIÊNCIA MOBILE
Seguir a arte aprovada: marca oficial; fotos reais; cards modernos; ofertas chamativas; verde + laranja + coral + amarelo; fundo creme; navegação simples.
Categorias: Todos; Refeições; Padaria; Frutas e Verduras; Mercado; Pizza; Café; outras.
Tela inicial: localização; busca; ofertas; descontos; fotos; estoque; retirada; delivery.
Menu inferior: Início; Ofertas; Pedidos; Favoritos; Perfil.

## 14. CHECKOUT
1 encontra oferta; 2 abre; 3 valida estoque; 4 escolhe quantidade; 5 retirada ou entrega; 6 calcula total; 7 paga; 8 cria pedido; 9 empresa recebe; 10 prepara; 11 confirma pronto; 12 Dispatch (se entrega); 13 entregador recebe; 14 coleta; 15 rota; 16 entrega; 17 confirmação; 18 repasse; 19 atualização de impacto.

## 15. PEDIDO
Estados: criado; aguardando pagamento; pago; recebido pela empresa; preparando; pronto; aguardando retirada; aguardando entregador; entregador designado; em coleta; em rota; entregue; retirado; concluído; cancelado; não retirado; expirado; destinado. Sempre manter histórico.

## 16. RETIRADA
Janela; endereço; instrução; pedido pronto; QR Code; PIN/código; confirmação; registro; prevenção contra duplicidade. Na chegada: pedido identificado; código validado; baixa; estoque atualizado; retirada registrada.

## 17. DISPATCH
Reaproveitar da base RMD Delivery: distância; disponibilidade; ETA; zona; capacidade; fallback. Acrescentar: janela de retirada; risco de expiração; prioridade da oferta e da coleta; agrupamento; compatibilidade de janelas; custo da rota; risco de perda; tempo máximo. Objetivo: priorizar pedidos de alimentos com janela limitada.

## 18. ENTREGADORES
Online/offline; receber oferta; aceitar; recusar; iniciar rota; chegar na coleta; confirmar coleta; transportar; entregar; confirmar entrega; GPS; histórico; ganhos; rotas agrupadas; suporte. Entregador próprio, entregador Sobrou+ ou parceiro externo.

## 19. FINANCEIRO
Reaproveitar: GMV; taxas; repasses; conciliação. Acrescentar: preço normal; desconto; preço Sobrou+; valor líquido; taxa Sobrou+; custo de entrega; comissão; custo operacional; economia do cliente; receita recuperada do parceiro. Mostrar: quanto o consumidor economizou; quanto o parceiro recuperou; quanto a plataforma faturou; quanto foi gasto com entrega; quanto deve ser repassado.

## 20. DOAÇÃO / DESTINAÇÃO
Doação real NÃO pode ser concluída sem: instituição cadastrada e autorizada; aceite; registro; quantidade; data; hora; origem; responsável; confirmação de coleta; confirmação da destinação.
Fluxo: oferta sem venda → encerramento → decisão de destinação → instituição → aceite → coleta → entrega → confirmação → registro de impacto.

## 21. IMPACTO
Indicadores: kg recuperados; unidades recuperadas; pedidos; economia dos clientes; receita recuperada dos parceiros; alimentos destinados; instituições atendidas; pessoas beneficiadas; ofertas recuperadas; desperdício evitado. Dashboard com gráficos e mapa.

## 22. SEGURANÇA / MULTIEMPRESA
Uma empresa NÃO pode acessar os dados privados de outra. Separação por plataforma, empresa, unidade, operador, financeiro, logística, parceiro, entregador, cliente, instituição.
Permissões: administrador Sobrou+; operador Sobrou+; administrador da empresa; operador da empresa; financeiro; logística; entregador; cliente; instituição.
Auditar: preço; estoque; pedido; cancelamento; alteração de oferta; repasse; doação; permissões; usuário; configuração.

## 23. FOTOGRAFIAS
Foto real, boa iluminação, comida apetitosa, upload pelo parceiro, compressão, thumbnail, imagem principal, múltiplas fotos. Sem cartoon. Categorias: refeições; pizza; padaria; frutas; verduras; mercado; sushi; doces; bebidas; cesta surpresa.

## 24. DESIGN / UX
Parecer empresa real, plataforma profissional, startup food-tech, marketplace grande, moderno, limpo, chamativo, comercial. NÃO parecer blog, jornal, sistema escolar, protótipo infantil, genérico ou sem identidade. Hierarquia visual; cards; fotos; indicadores; gráficos; botões claros; chamadas de oferta; status visíveis; bom uso das cores.

## 25. O QUE JÁ FOI EXECUTADO (pelo ChatGPT)
V1: estrutura central; dashboard; empresas; ofertas; pedidos; Dispatch visual; entregadores; clientes; doações; financeiro; relatórios; configurações; mobile; busca; cadastro demonstrativo de oferta; fotografia; fluxo visual.
V2: logomarca oficial aprovada; identidade visual alinhada à arte; paleta mais vibrante; fotos reais; dashboard mais próximo da arte; preview mobile; ofertas em destaque.

## 26. ESTADO REAL ATUAL (informado no combinado)
Protótipo/experiência demonstrável ~90%. Sistema comercial completo ~55% (estimativa). UI avançado; regras do protótipo avançadas; mapeamento da arquitetura RMD feito. Banco/API, pagamento, GPS/mapas, WhatsApp/notificações, conciliação e doação reais: NÃO CONECTADOS. QA ponta a ponta: não concluído.

## 27. TAREFAS PARA O CLAUDE (nesta ordem)
1 Localizar a base REAL do RMD Delivery (código, backend, Supabase, Postgres, API, migrations, autenticação, storage). 2 Backup, identificar commit, preservar original. 3 Criar projeto independente `SobrouPlus`. 4 NÃO alterar o RMD Delivery. 5 Copiar só infraestrutura real e comprovada. 6 Mapear entidades. 7 Criar estruturas específicas (excedente, estoque, validade, janela, desconto, preço inteligente, cesta surpresa, kit, instituições, doações, impacto). 8 Autenticação. 9 RBAC. 10 Multiempresa seguro. 11 Cadastro real de oferta. 12 Upload real de foto. 13 Estoque real. 14 Validade real. 15 Retirada real. 16 Checkout. 17 Pagamento. 18 Webhooks. 19 Pedidos. 20 Dispatch real. 21 GPS/telemetria. 22 Mapa real. 23 Notificações. 24 WhatsApp transacional. 25 Financeiro. 26 Repasses. 27 Conciliação. 28 Doação real. 29 Impacto. 30 Auditoria. 31 Logs. 32 QA. 33 Teste ponta a ponta.

## 28. CRITÉRIO DE PRONTO
Não declarar pronto só porque a tela existe. Testar: CLIENTE oferta → compra → pagamento → pedido. EMPRESA recebe → prepara → pronto. DISPATCH pedido → entregador → coleta → rota → entrega. FINANCEIRO cobrança → taxa → repasse → conciliação. ANTISSOBRA estoque → janela → expiração → desconto → venda → baixa. DOAÇÃO não vendida → instituição → aceite → coleta → destinação → registro. IMPACTO venda → kg → indicador. SEGURANÇA empresa A não acessa empresa B.

## 29. REGRA DE VERDADE
Estados permitidos: IMPLEMENTADO E VALIDADO; IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL; PARCIAL; PENDENTE; BLOQUEADO POR DEPENDÊNCIA. Não inventar integração, pagamento, GPS, doação, estoque, webhook, API, Supabase ou dados reais.

## 30. ARQUIVOS DE REFERÊNCIA
SobrouPlus_Logo_Aprovada.png; SobrouPlus_V2_Identidade_Aprovada.html; COMBINADO_SOBROUPLUS_PARA_CLAUDIO_2026-10-02.md; SobrouPlus_Sistema_V1_RMD_Base.html.

## 31. REGRA VISUAL DEFINITIVA
Logo oficial; foto real; visual food-tech; verde como identidade; laranja, coral/vermelho e amarelo como acentos; destaque para desconto, preço, estoque, oportunidade, urgência, expiração, compra. Não deixar tudo verde e branco. Sem desenho infantil. Interesse visual no alimento sem poluir.

## 32. REGRA DE INDEPENDÊNCIA
RMD Delivery original: NÃO ALTERAR. Sobrou+: NOVO SISTEMA. Código copiado deve ser identificado e adaptado no novo projeto. Não reaproveitar banco de forma destrutiva. Não misturar dados entre sistemas.



## 35. CONTINUIDADE OPERACIONAL E AMBIENTES — IMPLEMENTADO EM 08/10/2026
Foi criada uma camada de manutenção operacional sem alterar pagamentos, 2FA ou regras de negócio.

### Backup + restauração testada
- Backup SQLite consistente usando o mecanismo nativo do SQLite.
- Backup diário automático na inicialização, quando ainda não houver backup do dia.
- Cada backup recebe SHA-256 e metadados.
- O backup é copiado para um arquivo temporário e submetido a `PRAGMA integrity_check` antes de ser considerado válido.
- O teste executado em 08/10/2026 confirmou: backup criado, restauração/teste confirmado e `integrity_check=ok`.

### Monitoramento de integridade
- Manifesto SHA-256 dos arquivos críticos do backend/frontend.
- A cada inicialização, o sistema compara os arquivos com a última verificação.
- Alterações ou arquivos críticos ausentes ficam registrados no resultado da verificação.
- Banco também passa por `PRAGMA integrity_check`.

### Logs e retenção
- Auditoria existente continua sendo preservada.
- Retenção padrão da auditoria: 365 dias.
- Logs de arquivo: retenção padrão de 180 dias.
- Limpeza ocorre automaticamente na rotina de manutenção.

### Sessões administrativas
- A revogação de todas as sessões já está disponível.
- Alteração de senha revoga as demais sessões, mantendo apenas a sessão atual.
- Sessões expiradas são removidas automaticamente.

### Separação Desenvolvimento x Produção
- Produção: `data\\`, porta 8095, launcher `Sobrou+ (producao).bat` / `Sobrou+ (real).bat`.
- Desenvolvimento: `data_desenvolvimento\\`, porta 8096, launcher `Sobrou+ (desenvolvimento).bat`.
- O ambiente de desenvolvimento recebeu uma cópia inicial do banco de produção no momento da implantação; depois disso são bases independentes.
- A regra é testar alterações em desenvolvimento primeiro e somente depois atualizar produção.
- O RMD Delivery original continua fora desse processo e não é alterado.

### Não incluído nesta etapa
- 2FA/TOTP permanece adiado por decisão do projeto.
- Pagamento real/Mercado Pago permanece sem alteração nesta etapa.
- Senha atual do proprietário permanece sem alteração.

## 33/34. RESULTADO E DECISÃO FINAL
SOBROU+ = RMD Delivery como base operacional + marketplace antissobra + gestão inteligente de excedentes + delivery/retirada + preço e estoque por janela + cesta surpresa + doação/destinação + impacto social + identidade visual oficial Sobrou+, SEM ALTERAR O RMD DELIVERY ORIGINAL.

## 2026-10-09 — Claude — Sobrou+: verificação, limpeza e correções de segurança
- Pasta em uso: `Desktop\ALFA\modules\sobrouplus` (versão 0.2.0). A pasta antiga `Desktop\SobrouPlus` é só da versão 0.1.0.
- Senha: o código já usa a senha inicial padrão 1234 (regra do Rinaldo). Os 4 testes que ainda esperavam senha aleatória foram atualizados.
- Limpeza (nada apagado): 20 sobras (17 cópias .bak, 2 scripts de teste soltos, perfil de navegador `.edge_perfil_demo`) foram para `sobrouplus\_para_apagar`; as pastas antigas `sobrou`, `web` e `tests` da 0.1.0 foram para `Desktop\SobrouPlus\_para_apagar`. Pode apagar as duas pastas `_para_apagar` quando quiser.
- Revisão de segurança feita com ataques reais numa cópia de teste. Pontos fortes confirmados: isolamento entre empresas, papéis, CSRF, SQL, caminhos de arquivo, upload de fotos, telas sem injeção, webhook do Mercado Pago com assinatura, preço/estoque calculados no servidor.
- Corrigido:
  1. Limite de tentativas de senha não pode mais ser burlado pelo cabeçalho X-Forwarded-For (usa o último IP, o do túnel). `web/app.py`
  2. Bloqueio por erro de senha agora vale para e-mail + IP: quem ataca não bloqueia mais o acesso do Desenvolvedor RMD; e-mail inexistente responde igual (mesmo tempo e mesma mensagem). `sobrou/contas.py`, `sobrou/seguranca.py`
  3. Financeiro da loja não marca mais a própria mensalidade nem repasse como pago/calculado — só a equipe Sobrou+. `sobrou/extras.py`, `sobrou/financeiro.py`
  4. Travamento: envio com tamanho negativo recusado, tempo máximo de 30 s por conexão, limite nas rotas públicas (telemetria, webhooks) e limpeza das listas de limite. `web/app.py`
  5. Convite por WhatsApp/e-mail voltava erro 500 (linha presa em comentário) — corrigido. `web/app.py`
  6. Código de 4 dígitos da entrega: 5 erros travam a corrida por 15 min; retirada no balcão também tem limite. `sobrou/logistica.py`, `sobrou/pedidos.py`
  7. Relatórios CSV não levam mais fórmulas para o Excel. `sobrou/extras.py`
  8. Tokens do WhatsApp/e-mail guardados com a proteção do Windows (DPAPI); um backup levado a outro computador não revela os tokens (lá será preciso colar de novo). `sobrou/integracoes.py`
  9. Endereços de mapas (só https da internet) e servidor de e-mail não podem apontar para a rede interna. `sobrou/integracoes.py`
  10. "Sair" e "Entrar" também conferem a origem (outro site não desloga a pessoa); X-Forwarded-Host só é aceito do proxy confiável.
  11. Com túnel (atalhos de produção, `SOBROU_ATRAS_DE_PROXY=1`) o servidor só atende o próprio computador; o celular usa o endereço https. `SOBROU_REDE_LOCAL=1` libera o Wi-Fi se precisar. `web/iniciar.py`
  12. Para Railway: `SOBROU_PROXY_HOSPEDAGEM=1` faz o sistema reconhecer o HTTPS da hospedagem (cookie Secure e limite por pessoa). A cópia da Railway (dados fictícios) ainda NÃO foi publicada com as correções.
- Testes: 58 aprovados (10 novos em `tests/test_seguranca_correcoes.py`, um para cada ataque). Ainda falta rodar `Testar Sobrou+.bat` no Windows (a proteção DPAPI só funciona lá).
- Cópias dos arquivos originais: `sobrouplus\backup_seguranca_20261009\`.
- Fica para decidir: o cadastro de cliente ainda avisa "já existe uma conta com este e-mail" (normal em apps). Com ataques vindos de muitos lugares, uma conta que nunca trocou o 1234 ainda pode ser adivinhada — recomendação: trocar a senha no primeiro acesso.
- Para valer: fechar e abrir o Sobrou+ de novo.
