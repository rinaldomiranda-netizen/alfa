# Arquitetura de Módulos do ALPHA

O ALPHA passa a ser a plataforma-mãe da RMD. Os produtos funcionais entram como módulos isolados, compartilhando apenas os serviços de plataforma necessários.

## Núcleo compartilhado
- identidade e autenticação
- empresas/organizações (tenant)
- usuários, papéis e permissões
- segurança e auditoria
- configuração e planos/licenças
- navegação e shell do ALPHA
- notificações e serviços comuns
- descoberta de módulos por manifesto

## Módulos
1. `rmd-atendimento` — RMD Atendimento V5.1.1.
2. `pesquisa` — Central de Pesquisas Online.
3. `pesquisa-eleitoral` — Pesquisa Eleitoral/Pesquisas 2.0.
4. `ponto-facial` — módulo de ponto facial, preservado.
5. `obra360` — RMD Obra360, preservado.

Cada módulo mantém suas regras, telas, dados e APIs isolados. O módulo pode ser executado pelo ALPHA ou em modo standalone, usando o mesmo núcleo funcional.

## Regra de segurança
Esta primeira etapa é somente aditiva: nenhum código existente do ALPHA/BETA é substituído. A descoberta é feita por manifestos e a execução continua subordinada ao Skill Registry, Tool Registry e Permission Manager já existentes.

## Migração
A migração dos produtos será incremental. Primeiro registramos o módulo e seu contrato; depois conectamos a entrada visual; somente então migramos código funcional específico. Isso evita danificar o ALPHA/BETA existente.
