package com.beta.mobile.licensing

/** Módulos licenciáveis (item do pedido) — DEFAULT DENY: um módulo só
 * fica disponível se `GerenciadorLicenca` confirmar autorização (por
 * uma licença real assinada, ou pelo conjunto fixo do modo DEMO). */
enum class Modulo {
    TOTEM, APLICATIVO, ASSISTENTE, DESKTOP, INTEGRACAO_EMPRESA, CATALOGO,
    AUTOMACAO, ACESSIBILIDADE, CAMERA, RECONHECIMENTO_FACIAL, BETA_CLOUD,
    MARKETPLACE, ATUALIZACAO,
    // Adicionados no pedido "AUTORIZAÇÃO DIGITAL SEM CÓDIGO DE ATIVAÇÃO"
    // — nunca remover os módulos acima: licenças já emitidas referenciam
    // esses nomes pelo texto do enum, e removê-los mudaria silenciosamente
    // a autorização de uma licença antiga já assinada.
    VOZ, CAMERA_PRESENCA, CAMERA_CONTAGEM, PONTO_FUNCIONARIO, PAGAMENTO,
    // Adicionados no pedido "ORDEM MESTRA DE ACELERAÇÃO E FECHAMENTO" —
    // catálogo completo de módulos (item 6). Mesma regra: nunca remover
    // um nome já existente.
    CORE, MOBILE, PORTATIL, CASA, FAMILIA, KIDS, JOVEM, CUIDADOS, PET,
    SEGURANCA, EMERGENCIA, TRABALHO, APRESENTACAO, ATENDIMENTO, VENDAS,
    ESTOQUE, AVATAR_AVANCADO, SKILLS,
}

/** Pacotes comerciais (item do pedido: "Pacote = conjunto de
 * módulos") — cada pacote é só um atalho para um `Set<Modulo>` na
 * hora de emitir uma licença (ver licensing_tools/emitir_licenca.py
 * --pacote). Nunca é um mecanismo de autorização à parte: o que vale
 * pra `GerenciadorLicenca` continua sendo sempre `Licenca.modules`. */
enum class Pacote(val modulos: Set<Modulo>) {
    BETA_START(setOf(Modulo.ASSISTENTE, Modulo.APLICATIVO, Modulo.ACESSIBILIDADE)),
    BETA_PROFESSIONAL(setOf(Modulo.ASSISTENTE, Modulo.APLICATIVO, Modulo.ACESSIBILIDADE, Modulo.CATALOGO, Modulo.ATENDIMENTO, Modulo.VENDAS)),
    BETA_TOTEM(setOf(Modulo.TOTEM, Modulo.CATALOGO, Modulo.ATENDIMENTO, Modulo.VENDAS, Modulo.ESTOQUE, Modulo.ACESSIBILIDADE)),
    BETA_BUSINESS(setOf(Modulo.APLICATIVO, Modulo.TOTEM, Modulo.CATALOGO, Modulo.ATENDIMENTO, Modulo.VENDAS, Modulo.ESTOQUE, Modulo.INTEGRACAO_EMPRESA, Modulo.PONTO_FUNCIONARIO, Modulo.PAGAMENTO)),
    BETA_FAMILY(setOf(Modulo.ASSISTENTE, Modulo.CASA, Modulo.FAMILIA, Modulo.KIDS, Modulo.JOVEM, Modulo.CUIDADOS, Modulo.PET, Modulo.ACESSIBILIDADE)),
    BETA_SECURITY(setOf(Modulo.SEGURANCA, Modulo.EMERGENCIA, Modulo.CAMERA_PRESENCA, Modulo.CAMERA_CONTAGEM)),
    BETA_ENTERPRISE(Modulo.values().toSet() - setOf(Modulo.KIDS, Modulo.JOVEM, Modulo.PET)),
    BETA_CUSTOM(emptySet()),
}

/** Hierarquia de autoridade (item do pedido) — PUBLIC/OPERATOR/
 * BETA_DEVELOPER já têm um gate de PIN real nesta entrega (ver
 * MainActivity: botão de manutenção / área do desenvolvedor).
 * BETA_OWNER ganha o gate de senha nesta entrega (ver
 * CredencialProprietario.kt). COMPANY_ADMIN existe aqui como CONCEITO
 * (enum) mas ainda não tem uma tela própria — não há hoje um sistema
 * multiempresa real para administrar (ver limitações do relatório). */
enum class Nivel { PUBLIC, OPERATOR, COMPANY_ADMIN, BETA_DEVELOPER, BETA_OWNER }
