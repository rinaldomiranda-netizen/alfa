"""
Integration Adapter — camada genérica para a BETA operar sobre
sistemas comerciais/ERPs/CRMs/bancos de dados já existentes de uma
empresa (FASE C da expansão de plataforma — ver item 14 do pedido).

    BETA -> IntegrationAdapter -> sistema da empresa -> resultado -> Verifier -> resposta

Ordem de tentativa dentro de um adaptador concreto: API oficial, se
existir -> UI Automation, se não houver API -> OCR/visão, como último
recurso (ver vision/screen_vision.py, computer/form_filler.py —
reaproveitados pelo adaptador real quando existir, nunca duplicados
aqui). Este módulo só define o CONTRATO; nenhum adaptador real vem
configurado por padrão.

NUNCA inventa produto, preço ou estoque (item 16 do pedido): sem um
adaptador de verdade configurado e respondendo, o resultado é sempre
"integração não configurada" — nunca um dado fabricado (item 29:
"não criar sistemas fictícios que apenas parecem funcionar").
"""

from abc import ABC, abstractmethod


class ResultadoIntegracao:
    """Resultado de UMA consulta/operação num sistema externo.

    `fonte` registra COMO o dado foi obtido ("api" | "ui_automation" |
    "ocr") — nunca None quando sucesso=True, para o Verifier e a
    resposta ao usuário poderem indicar a origem quando fizer sentido.
    """

    def __init__(self, sucesso, mensagem, dados=None, fonte=None):
        self.sucesso = sucesso
        self.mensagem = mensagem
        self.dados = dados or {}
        self.fonte = fonte

    def __repr__(self):
        return f"ResultadoIntegracao(sucesso={self.sucesso}, fonte={self.fonte}, mensagem={self.mensagem!r})"


class IntegrationAdapter(ABC):
    """
    Interface que todo adaptador de sistema comercial/ERP/CRM precisa
    implementar. `categoria_permissao` decide se a ação exige
    confirmação (ver security/permissions.py) — tipicamente COMMERCIAL
    para consulta (não exige por si só) e PAYMENT para qualquer
    operação de pagamento (sempre exige, ver devices/base.py).
    """

    nome = "adaptador_generico"
    categoria_permissao = "COMMERCIAL"

    @abstractmethod
    def disponivel(self):
        """True só se o sistema alvo estiver de fato acessível agora
        (API respondendo, janela aberta, processo rodando) — nunca
        assume sem checar."""
        raise NotImplementedError

    @abstractmethod
    def consultar_produto(self, termo_busca):
        """
        Retorna ResultadoIntegracao. Implementações reais tentam,
        nesta ordem: API oficial -> UI Automation -> OCR (ver
        docstring do módulo). Múltiplos resultados: devolver todos em
        `dados["itens"]` para quem chamar perguntar qual o usuário
        quer (item 16) — nunca escolher um sozinho.
        """
        raise NotImplementedError


class AdaptadorNaoConfigurado(IntegrationAdapter):
    """
    Adaptador "nulo" — devolvido por IntegrationRegistry quando nenhum
    adaptador real foi configurado para este perfil/ambiente. Sempre
    honesto: nunca finge ter consultado nada.
    """

    nome = "nao_configurado"
    categoria_permissao = "COMMERCIAL"

    def disponivel(self):
        return False

    def consultar_produto(self, termo_busca):
        return ResultadoIntegracao(
            False,
            "Nenhuma integração com sistema comercial está configurada neste ambiente.",
        )
