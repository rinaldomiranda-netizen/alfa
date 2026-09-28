import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

from modules.atendimento_church.modulo import AtendimentoChurchModule, CONFIG_PADRAO
from modules.atendimento_church.service import AtendimentoChurchService
from modules.atendimento_church.store import ChurchCloudIndisponivel, ChurchStore
from modules.atendimento_church.ui import criar_app_wsgi, renderizar_painel


class TestChurchStore(unittest.TestCase):
    def test_nao_configurado_sem_credenciais(self):
        store = ChurchStore(url="", service_role_key="")
        self.assertFalse(store.configurado)
        with self.assertRaises(ChurchCloudIndisponivel):
            store.listar_conversas()

    @patch("modules.atendimento_church.store.requests")
    def test_listar_conversas_configurado(self, requests_mock):
        resposta = MagicMock()
        resposta.json.return_value = [{"data": {"id": "1", "n": "Fulano"}}]
        requests_mock.get.return_value = resposta
        store = ChurchStore(url="https://x.supabase.co", service_role_key="chave", igreja_id="igreja-1")
        resultado = store.listar_conversas()
        self.assertEqual(resultado, [{"id": "1", "n": "Fulano"}])
        chamada = requests_mock.get.call_args
        self.assertIn("church_conversations", chamada.args[0])
        self.assertEqual(chamada.kwargs["params"]["igreja_id"], "eq.igreja-1")

    @patch("modules.atendimento_church.store.requests")
    def test_salvar_conversa_exige_id(self, requests_mock):
        store = ChurchStore(url="https://x.supabase.co", service_role_key="chave")
        with self.assertRaises(ValueError):
            store.salvar_conversa({"n": "Sem id"})
        requests_mock.post.assert_not_called()


class TestAtendimentoChurchModule(unittest.TestCase):
    def test_offline_usa_config_padrao_e_lista_vazia(self):
        modulo = AtendimentoChurchModule(store=ChurchStore(url="", service_role_key=""))
        self.assertFalse(modulo.online)
        self.assertEqual(modulo.listar_conversas(), [])
        self.assertEqual(modulo.obter_config(), CONFIG_PADRAO)
        self.assertEqual(modulo.status()["id"], "rmd-atendimento-church")


class TestAtendimentoChurchService(unittest.TestCase):
    def test_exige_igreja_id(self):
        with self.assertRaises(ValueError):
            AtendimentoChurchService(igreja_id="")

    def test_estado_offline(self):
        servico = AtendimentoChurchService(
            igreja_id="igreja-1",
            modulo=AtendimentoChurchModule(store=ChurchStore(url="", service_role_key="")),
        )
        estado = servico.estado()
        self.assertFalse(estado["online"])
        self.assertEqual(estado["conversas"], [])
        self.assertEqual(estado["cfg"], CONFIG_PADRAO)


class FakeService:
    """Substitui AtendimentoChurchService nos testes do app WSGI."""

    def __init__(self):
        self.conversas_salvas = []
        self.config_salva = None

    def estado(self):
        return {"online": True, "conversas": [{"id": "1"}], "cfg": {"co": "Igreja Teste"}}

    def salvar_conversa(self, documento):
        if not documento.get("id"):
            raise ValueError("a conversa precisa ter 'id'")
        self.conversas_salvas.append(documento)
        return documento

    def salvar_config(self, documento):
        self.config_salva = documento
        return documento


def _chamar_wsgi(app, metodo, caminho, corpo=None):
    dados = json.dumps(corpo or {}).encode("utf-8")
    environ = {
        "REQUEST_METHOD": metodo,
        "PATH_INFO": caminho,
        "CONTENT_LENGTH": str(len(dados)),
        "wsgi.input": BytesIO(dados),
    }
    status_capturado = {}

    def start_response(status, headers):
        status_capturado["status"] = status
        status_capturado["headers"] = headers

    corpo_resposta = b"".join(app(environ, start_response))
    return status_capturado["status"], corpo_resposta


class TestChurchUi(unittest.TestCase):
    def test_renderiza_painel(self):
        html = renderizar_painel()
        self.assertIn("RMD Atendimento Church", html)
        self.assertIn("api/state", html)

    def test_api_state(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/api/state")
        self.assertEqual(status, "200 OK")
        dados = json.loads(corpo)
        self.assertTrue(dados["online"])
        self.assertEqual(dados["cfg"]["co"], "Igreja Teste")

    def test_api_conversa_grava(self):
        fake = FakeService()
        app = criar_app_wsgi(service=fake)
        status, corpo = _chamar_wsgi(app, "POST", "/api/conversa", {"id": "9", "n": "Maria"})
        self.assertEqual(status, "200 OK")
        self.assertTrue(json.loads(corpo)["ok"])
        self.assertEqual(fake.conversas_salvas, [{"id": "9", "n": "Maria"}])

    def test_api_conversa_sem_id_retorna_400(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "POST", "/api/conversa", {"n": "Sem id"})
        self.assertEqual(status, "400 Bad Request")
        self.assertFalse(json.loads(corpo)["ok"])

    def test_pagina_inicial(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"RMD Atendimento Church", corpo)

    def test_health(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/api/health")
        self.assertEqual(status, "200 OK")
        self.assertEqual(corpo, b"ok")


if __name__ == "__main__":
    unittest.main()
