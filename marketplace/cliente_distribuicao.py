"""
Cliente do serviço de distribuição de habilidades — FASE 5 da
expansão de plataforma (contrato):

    GET /skills
    GET /skills/<id>
    GET /skills/<id>/versions
    GET /updates/beta

Hoje NENHUM servidor real está configurado — toda chamada sem
`url_base` levanta ServicoIndisponivel, nunca inventa uma resposta
(item do pedido: "não criar sistemas fictícios que apenas parecem
funcionar"). Quando um servidor real existir, só configurar `url_base`
ativa o cliente; nada mais muda aqui nem em marketplace/pacotes.py, que
continua funcionando 100% com pacotes locais sem esta classe.
"""

import json
import urllib.request


class ServicoIndisponivel(Exception):
    pass


class ClienteDistribuicao:
    def __init__(self, url_base=None, timeout_segundos=10):
        self.url_base = url_base
        self.timeout_segundos = timeout_segundos

    def configurado(self):
        return bool(self.url_base)

    def _get(self, caminho):
        if not self.configurado():
            raise ServicoIndisponivel(
                "Nenhum serviço de distribuição configurado — use pacotes locais (ver marketplace/pacotes.py)."
            )
        url = self.url_base.rstrip("/") + caminho
        with urllib.request.urlopen(url, timeout=self.timeout_segundos) as resposta:
            return json.loads(resposta.read().decode("utf-8"))

    def listar_skills(self):
        """GET /skills"""
        return self._get("/skills")

    def obter_skill(self, id_skill):
        """GET /skills/<id>"""
        return self._get(f"/skills/{id_skill}")

    def versoes_skill(self, id_skill):
        """GET /skills/<id>/versions"""
        return self._get(f"/skills/{id_skill}/versions")

    def verificar_atualizacao_beta(self):
        """GET /updates/beta"""
        return self._get("/updates/beta")
