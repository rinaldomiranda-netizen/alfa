"""
Fundação do agente de computador da BETA (FASE 1 da evolução descrita
na auditoria arquitetural).

Pacote NOVO e aditivo — não substitui nada do pipeline de voz/comandos
existente (core/, computer/, voice/, vision/ continuam funcionando
exatamente como antes). Este pacote só COMBINA ferramentas que já
existem em torno de um Tool Registry, um contexto de sessão leve, um
planejador mínimo e uma camada de verificação, para provar que um
pedido composto ("abra o Word e escreva X") pode ser cumprido sem
cadastrar um comando específico para cada combinação possível.

    entender -> planejar -> usar ferramenta -> executar -> verificar
    -> continuar -> concluir

Módulos:
    ferramentas.py         Tool Registry (Ferramenta, ResultadoFerramenta, RegistroFerramentas)
    contexto.py             ContextoSessao (memória de curtíssimo prazo, só em RAM)
    verificador.py          funções de verificação (nunca inventam sucesso)
    descoberta_apps.py      localizar/abrir programas sem whitelist fixa
    ferramentas_arquivo.py  localizar/criar pasta/renomear arquivo
    registro_padrao.py      monta o registro reaproveitando componentes existentes
    planejador.py           Etapa, Tarefa, ExecutorDePlano
    orquestrador.py         primeiro fluxo real: "abrir app e escrever"
"""
