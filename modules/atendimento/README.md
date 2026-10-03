# RMD Atendimento — módulo oficial do ALFA

## Estado

**V5.2.0 — plataforma completa, conferida em 2026-09-25.**

Referência visual aprovada pelo Rinaldo: `docs/rmd_atendimento/prototipo_original_v5_1.html`.
As 17 telas do protótipo existem e funcionam de verdade (dados reais no banco, nada fixo na tela).

## Onde está cada parte

| Parte | Arquivo |
|---|---|
| Banco de dados (SQLite, multiempresa) | `modules/atendimento/plataforma/db.py` |
| Empresas, usuários, login, sessões, auditoria, configurações | `plataforma/nucleo.py`, `seguranca.py` |
| Perfis e permissões (conferidas pelo servidor em toda ação) | `plataforma/permissoes.py` |
| Nomes, filas, equipe, caixa de entrada, chat do site, portal do cliente | `plataforma/conversas.py` |
| Robô (fluxos com simulação antes de publicar) | `plataforma/fluxos.py` |
| Serviços, orçamentos (PDF/impressão, envio pelo WhatsApp), agenda | `plataforma/comercial.py` |
| WhatsApp oficial (Meta), API pública V1, webhooks de saída | `plataforma/canais.py` |
| Dashboard, alertas, relatórios, backup, plano & limites | `plataforma/gestao.py` |
| Empresa de demonstração (Laboratório de Módulos) | `plataforma/demo.py` |
| Servidor web e telas | `atendimento_web/app.py`, `atendimento_web/static/` |
| Abrir pelo ALFA (janela própria, perfil escolhido) | `atendimento_web/launcher.py` |
| Recepção por roteiro (protocolo antigo, continua funcionando) | `core/atendimento.py`, `modulo.py`, `service.py`, `store.py`, `atendimento_web/recepcao.py` |

## Perfis

| Perfil do Laboratório | Perfil no Atendimento | O que vê |
|---|---|---|
| ALFA OWNER / ADMIN | owner | Tudo + menu Empresas (todas as empresas clientes) |
| ADMINISTRADOR DO CLIENTE | admin | Tudo da própria empresa |
| FUNCIONÁRIO | atendente | Dashboard, Atendimento (só a própria fila), Nomes, Orçamentos, Agenda, Alertas |
| CLIENTE / USUÁRIO FINAL | cliente | Só "Minha área": conversa, orçamentos (aprovar/recusar) e agendamentos |

Também existe o perfil **supervisor** (gestão de equipe, relatórios e fluxos em modo leitura).

## Modos

- **Dentro do ALFA:** Laboratório de Módulos → RMD Atendimento → perfil. Abre numa janela do ALFA já logado.
- **Separado:** `python atendimento_web/app.py` → abre em `http://127.0.0.1:8080`. No primeiro acesso,
  o código que aparece na janela do servidor cria a empresa e o administrador. Só biblioteca padrão do Python.

## Dados

Ficam em `data/rmd_atendimento/` (banco `atendimento.db` e `backups/`). Essa pasta está no `.gitignore`:
dados de clientes nunca vão para o GitHub. Backup automático diário (30 guardados).

## Segurança

Servidor só para este computador por padrão (127.0.0.1); senhas PBKDF2; sessão em cookie HttpOnly/SameSite;
proteção CSRF; cabeçalhos de segurança (CSP); a empresa sempre vem da sessão, nunca do navegador;
webhooks só para HTTPS externo; assinatura HMAC da Meta conferida em toda mensagem recebida;
pedido de exclusão de dados (LGPD) em Nomes.

## Testes

```
python -m unittest tests.test_atendimento_plataforma atendimento_web.test_app tests.test_modulo_atendimento modules.atendimento.test_service modules.atendimento.test_service_finalizacao tests.test_atendimento
```
