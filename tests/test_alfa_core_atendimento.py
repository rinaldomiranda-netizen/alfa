"""
Testes de integração do modo atendimento no nível do AlfaCore:
encadeamento automático para o próximo atendimento, válvula de
segurança do operador ("encerrar atendimento" interrompe a fila) e
tratamento de "não entendi" quando o reconhecimento de voz falha.

Constrói o AlfaCore via __new__ (sem rodar __init__) e liga só as
peças necessárias, todas mockadas — nunca instancia motores reais de
voz/UI Automation/câmera, então é seguro e rápido.
"""

import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core.alfa_core import AlfaCore
from core.atendimento import AtendimentoBeta
from core.intent_engine import IntentEngine
from core.personality import Personality
from memory import memory


def _core_minimo():
    core = AlfaCore.__new__(AlfaCore)
    core.personality = Personality(nome_usuario="Rinaldo", nome_assistente="Beta")
    core.voice_output = MagicMock()
    core.voice_engine = MagicMock()
    core.intent_engine = IntentEngine()
    core.router = MagicMock()
    core.atendimento = AtendimentoBeta(camera_module=None, pesquisa_app=None)
    core._ultimo_roteiro_atendimento = None
    return core


_TMP_ATENDIMENTOS = None
_PATCHER_PASTA_ATENDIMENTOS = None


def setUpModule():
    # Alguns fluxos aqui chegam a "finalizado" e o AlfaCore real grava
    # os dados via memory.salvar_atendimento — nunca deve escrever na
    # pasta real memory/atendimentos/ do projeto durante os testes.
    global _TMP_ATENDIMENTOS, _PATCHER_PASTA_ATENDIMENTOS
    _TMP_ATENDIMENTOS = tempfile.TemporaryDirectory()
    _PATCHER_PASTA_ATENDIMENTOS = patch.object(memory, "PASTA_ATENDIMENTOS", _TMP_ATENDIMENTOS.name)
    _PATCHER_PASTA_ATENDIMENTOS.start()


def tearDownModule():
    _PATCHER_PASTA_ATENDIMENTOS.stop()
    _TMP_ATENDIMENTOS.cleanup()


class TestEncadeamentoAutomatico(unittest.TestCase):

    def test_finalizar_roteiro_encadeia_o_proximo_atendimento(self):
        core = _core_minimo()
        roteiro = [{"campo": "Idade", "pergunta": "Qual é a sua idade?", "tipo": "texto", "confirmar": False}]

        core._iniciar_atendimento(roteiro)
        core._processar_turno_atendimento("João")
        core._processar_turno_atendimento("sim")
        core._processar_turno_atendimento("35")  # finaliza e encadeia

        falas = [chamada.args[0] for chamada in core.voice_output.falar.call_args_list]
        self.assertTrue(any("Pronto, Seu João" in f for f in falas))
        self.assertTrue(any("novo atendimento" in f for f in falas))

        self.assertTrue(core.atendimento.esta_ativo())
        self.assertIsNone(core.atendimento.nome_pessoa)

    def test_atendimento_com_roteiro_vazio_tambem_encadeia(self):
        core = _core_minimo()
        core._iniciar_atendimento([])
        core._processar_turno_atendimento("Maria")
        core._processar_turno_atendimento("sim")  # identificação já finaliza (sem roteiro)

        self.assertTrue(core.atendimento.esta_ativo())
        self.assertIsNone(core.atendimento.nome_pessoa)


class TestValvulaDeSegurancaDoOperador(unittest.TestCase):

    def test_encerrar_atendimento_durante_a_fila_para_tudo_sem_encadear(self):
        core = _core_minimo()
        roteiro = [{"campo": "Idade", "pergunta": "Qual é a sua idade?", "tipo": "texto"}]
        core._iniciar_atendimento(roteiro)
        core._processar_turno_atendimento("João")
        core._processar_turno_atendimento("sim")

        # Simula o texto ouvido chegando como comando de encerrar,
        # passando pelo mesmo caminho que ciclo_unico usaria.
        intent = core.intent_engine.interpretar("encerrar atendimento")
        self.assertEqual(intent["intent"], "ENCERRAR_ATENDIMENTO")

        core._encerrar_atendimento(auto_prox=False)

        self.assertFalse(core.atendimento.esta_ativo())

    def test_ciclo_unico_intercepta_encerrar_atendimento_e_para_a_fila(self):
        core = _core_minimo()
        core._iniciar_atendimento([{"campo": "Idade", "pergunta": "Idade?", "tipo": "texto"}])
        core._processar_turno_atendimento("João")
        core._processar_turno_atendimento("sim")

        core.voice_engine.listen.return_value = ("encerrar atendimento", "whisper")
        core.ciclo_unico()

        self.assertFalse(core.atendimento.esta_ativo())
        core.router.handle.assert_not_called()

    def test_resposta_normal_da_pessoa_nao_e_confundida_com_comando_de_encerrar(self):
        core = _core_minimo()
        core._iniciar_atendimento([{"campo": "Cidade", "pergunta": "Qual sua cidade?", "tipo": "texto", "confirmar": False}])
        core._processar_turno_atendimento("João")
        core._processar_turno_atendimento("sim")

        intent = core.intent_engine.interpretar("Recife")
        self.assertNotEqual(intent["intent"], "ENCERRAR_ATENDIMENTO")


class TestNaoEntendiDuranteAtendimento(unittest.TestCase):

    def test_texto_vazio_durante_nome_fala_mensagem_especifica(self):
        core = _core_minimo()
        core.voice_engine.listen.return_value = ("", "whisper")
        core._iniciar_atendimento([])

        core.ciclo_unico()

        falas = [chamada.args[0] for chamada in core.voice_output.falar.call_args_list]
        self.assertTrue(any("repetir seu nome" in f for f in falas))
        core.router.handle.assert_not_called()

    def test_texto_vazio_fora_do_atendimento_nao_fala_nada(self):
        core = _core_minimo()
        core.voice_engine.listen.return_value = ("", "whisper")

        core.ciclo_unico()

        core.voice_output.falar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
