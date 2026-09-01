"""
Device Adapter — camada genérica para equipamentos externos
(impressoras, leitores, displays, balanças, terminais de pagamento) —
FASE E da expansão de plataforma (ver item 17 do pedido).

PAGAMENTO NUNCA é processado aqui: um DeviceAdapter do tipo
"pagamento" só INICIA uma operação e aguarda confirmação explícita do
usuário, delegando o processamento de verdade a um SDK/API OFICIAL do
equipamento. Este módulo nunca implementa processamento próprio de
cartão nem guarda dado sensível de cartão (item 17: "não armazenar
dados sensíveis de cartão", "não implementar processamento próprio de
cartão").

Fluxo esperado para pagamento (ver core/alfa_core.py + security/
permissions.py -> CATEGORIA_PAYMENT, que SEMPRE exige confirmação):

    BETA -> sistema comercial -> cria operação -> DeviceAdapter (pagamento)
    -> usuário confirma no próprio equipamento -> resultado
    -> sistema comercial -> BETA informa o resultado
"""

from abc import ABC, abstractmethod

TIPOS_VALIDOS = ("impressora", "leitor", "display", "balanca", "pagamento", "generico")


class ResultadoDispositivo:
    def __init__(self, sucesso, mensagem, dados=None):
        self.sucesso = sucesso
        self.mensagem = mensagem
        self.dados = dados or {}

    def __repr__(self):
        return f"ResultadoDispositivo(sucesso={self.sucesso}, mensagem={self.mensagem!r})"


class DeviceAdapter(ABC):
    nome = "dispositivo_generico"
    tipo = "generico"

    @abstractmethod
    def disponivel(self):
        """True só se o equipamento estiver de fato conectado/
        respondendo agora — nunca assume."""
        raise NotImplementedError

    @abstractmethod
    def executar(self, operacao, **parametros):
        """
        Retorna ResultadoDispositivo. Para tipo == "pagamento", a
        implementação real:
          1. nunca executa por uma ordem conversacional simples sem
             confirmação (ver security/permissions.py -> PAYMENT);
          2. delega o processamento ao SDK/API oficial do equipamento;
          3. nunca guarda número de cartão, CVV ou dado sensível
             equivalente — só o resultado (aprovado/negado/id da
             transação).
        """
        raise NotImplementedError


class DispositivoNaoConfigurado(DeviceAdapter):
    """Devolvido por DeviceRegistry quando nenhum equipamento real foi
    configurado — nunca finge ter executado uma operação."""

    nome = "nao_configurado"
    tipo = "generico"

    def disponivel(self):
        return False

    def executar(self, operacao, **parametros):
        return ResultadoDispositivo(False, "Nenhum dispositivo está configurado para esta operação.")
