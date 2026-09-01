"""
Descobre e disponibiliza os adaptadores de integração (ver
integrations/base.py) configurados para o perfil atual. Sem nenhuma
configuração, devolve só o AdaptadorNaoConfigurado — nunca inventa uma
integração que não existe (ver core/alfa_core.py, que constrói UM
IntegrationRegistry por instância e nunca registra nada nele por
padrão).
"""

from integrations.base import AdaptadorNaoConfigurado


class IntegrationRegistry:
    def __init__(self):
        self._adaptadores = {}

    def registrar(self, adaptador):
        self._adaptadores[adaptador.nome] = adaptador

    def obter(self, nome=None):
        if nome:
            return self._adaptadores.get(nome, AdaptadorNaoConfigurado())
        if self._adaptadores:
            return next(iter(self._adaptadores.values()))
        return AdaptadorNaoConfigurado()

    def listar(self):
        return list(self._adaptadores.values())

    def alguma_configurada(self):
        return bool(self._adaptadores)
