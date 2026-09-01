"""
Roteiro REAL da tela "Nova entrevista" do projeto Central de
Pesquisas Online (Fase 2) — nada aqui foi inventado.

Fonte da verdade (localizada no computador do usuário, projeto
irmão deste):

    Desktop/Central_de_Pesquisas_Online_Fase2/Central_de_Pesquisas_Online/app.js
        renderInterviewFormPage()  -> desenha os campos (por volta da linha 8417)
        submitRMDInterview()       -> valida e grava a entrevista (por volta da linha 8897)

Campos reais da tela, na MESMA ordem em que aparecem (o HTML é
gerado dinamicamente por app.js; os `id` abaixo são os
`AutomationId` que o Chromium/Edge expõe ao Windows UI Automation
para cada elemento — a forma mais confiável de localizá-los):

    #rmdInterviewName          "Nome do entrevistado"   input texto   OBRIGATÓRIO
    #rmdInterviewPhone         "Telefone"                input texto   opcional
    #rmdInterviewRegion        rótulo dinâmico (padrão "Região")       select  opcional
    #rmdInterviewCongregation  rótulo dinâmico (padrão "Congregação")  select  opcional
    (sem id)                   "Intenção de voto" (pesquisa eleitoral)
                                ou "Resposta principal" (demais tipos) —
                                4 botões: "👍 Sim" / "👎 Não" / "🤔 Indeciso" /
                                "➖ Sem resposta"                        OBRIGATÓRIO
    #rmdInterviewReason        "Observações"             textarea      opcional

Botão final: "✓ Registrar entrevista" (chama submitRMDInterview()).
Essa tela é uma página única — não existem botões "Próximo"/
"Avançar" intermediários — por isso o roteiro não usa passos de
navegação no meio, só um passo final para clicar em "Registrar
entrevista".

Nenhuma foto é pedida por essa tela: por isso este roteiro NÃO
inclui nenhum passo do tipo "foto" — o mecanismo de câmera
(vision/camera.py) continua disponível para quando uma pesquisa real
exigir, mas não é usado aqui só porque existe.

Validação real (submitRMDInterview, lida do código-fonte):
    - sem nome            -> alerta "Informe o nome do entrevistado."
    - sem resposta/intenção -> alerta "Selecione a resposta principal."
    (telefone, região, congregação e observações são opcionais)

IMPORTANTE: submitRMDInterview() grava de verdade no banco Supabase
de produção configurado em config.js (DEMO_MODE = false). Concluir
este roteiro até o fim cria uma entrevista real.
"""

CAMPO_NOME = "Nome do entrevistado"
CAMPO_TELEFONE = "Telefone"
CAMPO_REGIAO = "Região"
CAMPO_CONGREGACAO = "Congregação"
CAMPO_RESPOSTA = "Resposta principal"
CAMPO_OBSERVACOES = "Observações"

ID_NOME = "rmdInterviewName"
ID_TELEFONE = "rmdInterviewPhone"
ID_REGIAO = "rmdInterviewRegion"
ID_CONGREGACAO = "rmdInterviewCongregation"
ID_OBSERVACOES = "rmdInterviewReason"

# Rótulos reais dos 4 botões de resposta (lidos literalmente de
# app.js, linhas ~8776-8818). O emoji faz parte do texto visível, mas
# não é necessário falar/entender — a busca por elemento já compara
# por substring ("sim" casa com "👍 Sim").
OPCOES_RESPOSTA_PRINCIPAL = ["Sim", "Não", "Indeciso", "Sem resposta"]

NOME_BOTAO_REGISTRAR = "Registrar entrevista"


def roteiro_nova_entrevista():
    """
    Devolve o roteiro real da tela "Nova entrevista" (ver docstring
    do módulo). É uma função — não uma constante — porque
    AtendimentoBeta muta a própria lista de respostas internamente a
    cada atendimento; reaproveitar a MESMA lista de passos entre
    atendimentos diferentes não teria problema (os passos em si não
    são alterados, só lidos), mas devolver uma lista nova a cada
    chamada evita qualquer risco de um módulo chamador alterar os
    dicts e afetar atendimentos futuros.
    """
    return [
        {
            "campo": CAMPO_NOME,
            "automation_id": ID_NOME,
            "pergunta": "Qual é o seu nome completo?",
            "tipo": "texto",
            "confirmar": True,
            "obrigatorio": True,  # submitRMDInterview: "Informe o nome do entrevistado."
        },
        {
            "campo": CAMPO_TELEFONE,
            "automation_id": ID_TELEFONE,
            "pergunta": "Qual é o seu telefone para contato?",
            "tipo": "texto",
            "confirmar": True,
            "obrigatorio": False,
        },
        {
            "campo": CAMPO_REGIAO,
            "automation_id": ID_REGIAO,
            "pergunta": None,  # lida dinamicamente da tela — ver AtendimentoBeta
            "tipo": "opcao",
            "confirmar": True,
            "obrigatorio": False,
        },
        {
            "campo": CAMPO_CONGREGACAO,
            "automation_id": ID_CONGREGACAO,
            "pergunta": None,
            "tipo": "opcao",
            "confirmar": True,
            "obrigatorio": False,
        },
        {
            "campo": CAMPO_RESPOSTA,
            "pergunta": None,  # monta a pergunta com OPCOES_RESPOSTA_PRINCIPAL abaixo
            "tipo": "opcao_botao",
            "opcoes": OPCOES_RESPOSTA_PRINCIPAL,
            "confirmar": True,
            "confirmar_template": "Você confirma que sua resposta é {valor}?",
            "obrigatorio": True,  # submitRMDInterview: "Selecione a resposta principal."
        },
        {
            "campo": CAMPO_OBSERVACOES,
            "automation_id": ID_OBSERVACOES,
            "pergunta": "Deseja registrar alguma observação sobre a entrevista?",
            "tipo": "texto",
            "confirmar": True,
            "obrigatorio": False,
        },
        {
            "tipo": "navegacao",
            "nome": NOME_BOTAO_REGISTRAR,
        },
    ]
