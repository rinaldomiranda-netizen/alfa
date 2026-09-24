# RMD Atendimento — módulo ALPHA

## Estado

**V5.1.1 — integrado ao ALPHA em `feat/modulos-rmd`.**

O protocolo de atendimento existente em `core/atendimento.py` continua sendo a implementação funcional. Este módulo adiciona uma fachada estável para que o ALPHA possa descobrir e abrir o atendimento sem duplicar a máquina de estados.

## O que já está preservado

- identificação da pessoa e confirmação do nome;
- roteiro pergunta → ouvir → confirmar → preencher → avançar;
- tratamento de respostas não entendidas;
- confirmação de dados antes de registrar;
- autorização quando exigida pelo roteiro;
- consentimento explícito para foto;
- prévia e refazer foto;
- associação da foto ao ID único do atendimento;
- limpeza completa do contexto ao encerrar;
- preparação do próximo atendimento;
- uso do roteiro real de pesquisa quando o módulo de pesquisa estiver disponível;
- integração com câmera e preenchimento de formulário existentes;
- testes unitários do protocolo e da fachada.

## Arquitetura

`modules/atendimento/modulo.py` é uma fachada. Ela não copia regras de `core/atendimento.py`; apenas encaminha a sessão para a implementação existente. Isso evita duas máquinas de atendimento concorrentes e mantém compatibilidade com o fluxo atual da Beta.

## Modos

- **Alpha:** o módulo é descoberto pelo Skill Registry e pode ser usado pela plataforma.
- **Standalone:** a mesma fachada pode ser instanciada sem o menu do Alpha, mantendo as mesmas regras funcionais.

## Segurança e isolamento

O módulo não recebe credenciais próprias e não altera o Alpha Core. Permissões e ferramentas continuam sob os mecanismos existentes do ALPHA. Os dados locais do atendimento permanecem no mecanismo de memória já utilizado pelo projeto.
