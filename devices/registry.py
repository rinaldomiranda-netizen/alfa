"""
Descobre e disponibiliza os DeviceAdapter (ver devices/base.py)
configurados para o perfil atual. Sem nenhuma configuração, devolve só
o DispositivoNaoConfigurado — nunca inventa um equipamento conectado.
"""

from devices.base import DispositivoNaoConfigurado


class DeviceRegistry:
    def __init__(self):
        self._dispositivos = {}

    def registrar(self, dispositivo):
        self._dispositivos[dispositivo.nome] = dispositivo

    def obter(self, nome=None):
        if nome:
            return self._dispositivos.get(nome, DispositivoNaoConfigurado())
        if self._dispositivos:
            return next(iter(self._dispositivos.values()))
        return DispositivoNaoConfigurado()

    def listar(self, tipo=None):
        dispositivos = list(self._dispositivos.values())
        if tipo:
            dispositivos = [d for d in dispositivos if d.tipo == tipo]
        return dispositivos

    def algum_configurado(self):
        return bool(self._dispositivos)
