import json
import os
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
        self.assertEqual(chamada.kwargs["params"]["limit"], "200")

    @patch("modules.atendimento_church.store.requests")
    def test_listar_conversas_respeita_limit(self, requests_mock):
        resposta = MagicMock()
        resposta.json.return_value = []
        requests_mock.get.return_value = resposta
        store = ChurchStore(url="https://x.supabase.co", service_role_key="chave")
        store.listar_conversas(limit=5000)  # acima do máximo: deve ser limitado
        chamada = requests_mock.get.call_args
        self.assertEqual(chamada.kwargs["params"]["limit"], "2000")

    @patch("modules.atendimento_church.store.requests")
    def test_salvar_conversa_exige_id(self, requests_mock):
        store = ChurchStore(url="https://x.supabase.co", service_role_key="chave")
        with self.assertRaises(ValueError):
            store.salvar_conversa({"n": "Sem id"})
        requests_mock.post.assert_not_called()

    def test_exportar_backup_offline_levanta_erro(self):
        store = ChurchStore(url="", service_role_key="")
        with self.assertRaises(ChurchCloudIndisponivel):
            store.exportar_backup()

    @patch("modules.atendimento_church.store.requests")
    def test_exportar_backup_configurado(self, requests_mock):
        resposta_conversas = MagicMock()
        resposta_conversas.json.return_value = [{"data": {"id": "1"}}]
        resposta_config = MagicMock()
        resposta_config.json.return_value = [{"data": {"co": "Igreja X"}}]
        requests_mock.get.side_effect = [resposta_conversas, resposta_config]
        store = ChurchStore(url="https://x.supabase.co", service_role_key="chave", igreja_id="igreja-1")
        pacote = store.exportar_backup()
        self.assertEqual(pacote["igreja_id"], "igreja-1")
        self.assertIn("gerado_em", pacote)
        self.assertEqual(pacote["conversas"], [{"id": "1"}])
        self.assertEqual(pacote["config"], {"co": "Igreja X"})


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

    def test_exportar_backup_offline_propaga_erro(self):
        servico = AtendimentoChurchService(
            igreja_id="igreja-1",
            modulo=AtendimentoChurchModule(store=ChurchStore(url="", service_role_key="")),
        )
        with self.assertRaises(ChurchCloudIndisponivel):
            servico.exportar_backup()


class FakeService:
    """Substitui AtendimentoChurchService nos testes do app WSGI."""

    def __init__(self, igreja_id="default"):
        self.igreja_id = igreja_id
        self.conversas_salvas = []
        self.config_salva = None

    def estado(self, limit=None):
        return {"online": True, "conversas": [{"id": "1"}], "cfg": {"co": "Igreja Teste"}}

    def salvar_conversa(self, documento):
        if not documento.get("id"):
            raise ValueError("a conversa precisa ter 'id'")
        self.conversas_salvas.append(documento)
        return documento

    def salvar_config(self, documento):
        self.config_salva = documento
        return documento

    def exportar_backup(self):
        return {"igreja_id": self.igreja_id, "gerado_em": "2026-01-01T00:00:00+00:00", "conversas": [], "config": {}}


def _chamar_wsgi(app, metodo, caminho, corpo=None, headers=None):
    dados = json.dumps(corpo or {}).encode("utf-8")
    if "?" in caminho:
        path_info, query_string = caminho.split("?", 1)
    else:
        path_info, query_string = caminho, ""
    environ = {
        "REQUEST_METHOD": metodo,
        "PATH_INFO": path_info,
        "QUERY_STRING": query_string,
        "CONTENT_LENGTH": str(len(dados)),
        "wsgi.input": BytesIO(dados),
    }
    environ.update(headers or {})
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
        self.assertNotIn("<script>window.IGREJA_ID=", html)

    def test_renderiza_painel_com_igreja_id(self):
        html = renderizar_painel("comunidade-x")
        self.assertIn('window.IGREJA_ID="comunidade-x"', html)

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

    def test_pagina_inicial_com_igreja_na_query(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/?igreja=comunidade-x")
        self.assertEqual(status, "200 OK")
        self.assertIn(b'window.IGREJA_ID="comunidade-x"', corpo)

    def test_health(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/api/health")
        self.assertEqual(status, "200 OK")
        self.assertEqual(corpo, b"ok")

    def test_backup_com_service_fixo(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/api/backup")
        self.assertEqual(status, "200 OK")
        dados = json.loads(corpo)
        self.assertEqual(dados["igreja_id"], "default")

    def test_backup_offline_retorna_503(self):
        servico = AtendimentoChurchService(
            igreja_id="igreja-1",
            modulo=AtendimentoChurchModule(store=ChurchStore(url="", service_role_key="")),
        )
        app = criar_app_wsgi(service=servico)
        status, corpo = _chamar_wsgi(app, "GET", "/api/backup")
        self.assertEqual(status, "503 Service Unavailable")


class TestChurchUiMultiTenant(unittest.TestCase):
    def test_resolve_igreja_id_da_query(self):
        recebidos = []

        def fabrica(igreja_id):
            recebidos.append(igreja_id)
            return FakeService(igreja_id=igreja_id)

        app = criar_app_wsgi(service_factory=fabrica)
        _chamar_wsgi(app, "GET", "/api/state?igreja=comunidade-x")
        self.assertEqual(recebidos, ["comunidade-x"])

    def test_resolve_igreja_padrao_quando_ausente(self):
        recebidos = []

        def fabrica(igreja_id):
            recebidos.append(igreja_id)
            return FakeService(igreja_id=igreja_id)

        app = criar_app_wsgi(service_factory=fabrica)
        _chamar_wsgi(app, "GET", "/api/state")
        self.assertEqual(recebidos, ["default"])

    def test_service_fixo_ignora_igreja_da_query(self):
        fake = FakeService(igreja_id="fixa")
        app = criar_app_wsgi(service=fake)
        status, corpo = _chamar_wsgi(app, "GET", "/api/backup?igreja=outra-igreja")
        self.assertEqual(status, "200 OK")
        self.assertEqual(json.loads(corpo)["igreja_id"], "fixa")


class TestChurchUiToken(unittest.TestCase):
    def setUp(self):
        self._token_anterior = os.environ.get("CHURCH_API_TOKEN")
        os.environ["CHURCH_API_TOKEN"] = "segredo-teste-123"

    def tearDown(self):
        if self._token_anterior is None:
            os.environ.pop("CHURCH_API_TOKEN", None)
        else:
            os.environ["CHURCH_API_TOKEN"] = self._token_anterior

    def test_bloqueia_sem_token(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/api/state")
        self.assertEqual(status, "401 Unauthorized")

    def test_libera_com_token_no_cabecalho(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(
            app, "GET", "/api/state", headers={"HTTP_X_CHURCH_TOKEN": "segredo-teste-123"}
        )
        self.assertEqual(status, "200 OK")

    def test_libera_com_token_na_query(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/api/state?token=segredo-teste-123")
        self.assertEqual(status, "200 OK")

    def test_health_nao_exige_token(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/api/health")
        self.assertEqual(status, "200 OK")

    def test_pagina_inicial_nao_exige_token(self):
        app = criar_app_wsgi(service=FakeService())
        status, corpo = _chamar_wsgi(app, "GET", "/")
        self.assertEqual(status, "200 OK")


class TestChurchStream(unittest.TestCase):
    def test_primeiro_evento_chega_com_o_estado_atual(self):
        app = criar_app_wsgi(service=FakeService())
        status_capturado = {}

        def start_response(status, headers):
            status_capturado["status"] = status
            status_capturado["headers"] = dict(headers)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/stream",
            "QUERY_STRING": "",
            "CONTENT_LENGTH": "0",
            "wsgi.input": BytesIO(b""),
        }
        gerador = app(environ, start_response)
        primeiro = next(iter(gerador))
        self.assertEqual(status_capturado["status"], "200 OK")
        self.assertEqual(status_capturado["headers"]["Content-Type"], "text/event-stream; charset=utf-8")
        self.assertTrue(primeiro.startswith(b"data:"))
        self.assertIn(b"Igreja Teste", primeiro)
        gerador.close()


if __name__ == "__main__":
    unittest.main()
