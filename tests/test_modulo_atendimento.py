import unittest

from modules.atendimento import AtendimentoModule
from core.atendimento import EstadoAtendimento


class TestAtendimentoModule(unittest.TestCase):
    def _modulo(self):
        return AtendimentoModule(camera_module=None, pesquisa_app=None)

    def test_inicia_e_expoe_status(self):
        modulo = self._modulo()
        mensagem = modulo.iniciar([])
        self.assertIn("Com quem estou falando?", mensagem)
        status = modulo.status()
        self.assertEqual(status["id"], "rmd-atendimento")
        self.assertEqual(status["versao"], "5.1.1")
        self.assertTrue(status["ativo"])
        self.assertEqual(status["estado"], EstadoAtendimento.AGUARDANDO_NOME.value)

    def test_identificacao_e_confirmacao_passam_pela_mesma_maquina(self):
        modulo = self._modulo()
        modulo.iniciar([])
        resultado = modulo.responder("Meu nome é João")
        self.assertEqual(resultado["acao"], "confirmar")
        self.assertIn("João", resultado["mensagem"])
        resultado = modulo.responder("sim")
        self.assertIn(resultado["acao"], {"aguardando_roteiro", "proxima_pergunta", "finalizado"})

    def test_limpar_remove_contexto_da_pessoa(self):
        modulo = self._modulo()
        modulo.iniciar([])
        modulo.responder("Meu nome é João")
        modulo.responder("sim")
        modulo.limpar()
        status = modulo.status()
        self.assertFalse(status["ativo"])
        self.assertIsNone(status["nome_pessoa"])
        self.assertIsNone(status["atendimento_id"])


if __name__ == "__main__":
    unittest.main()
