"""
Testes da camada de personalidade (core/personality.py).

Cobrem a separação pedida entre PERSONALIDADE e TEXTO/EXECUÇÃO: o
executor/roteador só produz fatos ("Mouse movido para a direita."),
e é a Personality quem decide o tom e a forma de entregar isso.
"""

import unittest
from unittest.mock import patch

from core.personality import Personality


class TestPersonalitySaudacaoEDespedida(unittest.TestCase):

    def setUp(self):
        self.personality = Personality(nome_usuario="Rinaldo", nome_assistente="Beta")

    @patch("core.personality.datetime")
    def test_saudacao_de_manha(self, mock_datetime):
        mock_datetime.now.return_value.hour = 9
        texto, estilo = self.personality.saudacao_inicial()
        self.assertEqual(
            texto, "Bom dia, Rinaldo. A Beta está pronta. Como posso ajudá-lo?"
        )
        self.assertEqual(estilo, "saudacao")

    @patch("core.personality.datetime")
    def test_saudacao_de_tarde(self, mock_datetime):
        mock_datetime.now.return_value.hour = 15
        texto, _ = self.personality.saudacao_inicial()
        self.assertEqual(texto, "Boa tarde, Rinaldo. A Beta está pronta.")

    @patch("core.personality.datetime")
    def test_saudacao_de_noite(self, mock_datetime):
        mock_datetime.now.return_value.hour = 21
        texto, _ = self.personality.saudacao_inicial()
        self.assertEqual(texto, "Boa noite, Rinaldo. Estou pronta para ajudá-lo.")

    def test_despedida(self):
        texto, estilo = self.personality.despedida()
        self.assertEqual(texto, "Até logo, Rinaldo.")
        self.assertEqual(estilo, "seria")


class TestPersonalityCompor(unittest.TestCase):

    def setUp(self):
        self.personality = Personality(nome_usuario="Rinaldo")

    def test_comando_local_bem_sucedido_e_confirmacao_calorosa(self):
        texto, estilo = self.personality.compor(
            {"intent": "MOVER_MOUSE"}, "Mouse movido para a direita."
        )
        self.assertEqual(estilo, "confirmacao")
        self.assertTrue(texto.endswith("Mouse movido para a direita."))
        self.assertIn("Rinaldo", texto)

    def test_aberturas_de_confirmacao_alternam_a_cada_chamada(self):
        _, _ = ("", "")
        texto1, _ = self.personality.compor({"intent": "CLIQUE"}, "Clique realizado.")
        texto2, _ = self.personality.compor({"intent": "CLIQUE"}, "Clique realizado.")
        abertura1 = texto1.split(",")[0]
        abertura2 = texto2.split(",")[0]
        self.assertNotEqual(abertura1, abertura2)

    def test_erro_usa_tom_empatico(self):
        texto, estilo = self.personality.compor(
            {"intent": "FECHAR", "programa": "xyz"}, "Não consegui abrir xyz: erro."
        )
        self.assertEqual(estilo, "empatica")
        self.assertIn("Rinaldo", texto)

    def test_comando_desconhecido_mantem_resposta_da_ia_intacta(self):
        resposta_ia = "Ha! Essa foi boa, Rinaldo."
        texto, estilo = self.personality.compor({"intent": "DESCONHECIDO"}, resposta_ia)
        self.assertEqual(texto, resposta_ia)
        self.assertEqual(estilo, "descontraida")

    def test_pedido_de_confirmacao_usa_tom_serio_sem_abertura_de_sucesso(self):
        intent = {
            "intent": "FECHAR",
            "programa": "calculadora",
            "_pedido_confirmacao": True,
        }
        texto, estilo = self.personality.compor(
            intent, "Tem certeza que deseja fechar calculadora? Diga 'sim' para confirmar."
        )
        self.assertEqual(estilo, "seria")
        self.assertTrue(texto.startswith("Rinaldo,"))
        self.assertNotIn("Claro", texto)

    def test_confirmacao_negada_tom_neutro_sem_alteracao_de_texto(self):
        texto, estilo = self.personality.compor(
            {"intent": "CONFIRMACAO_NEGADA"}, "Ação cancelada."
        )
        self.assertEqual(texto, "Ação cancelada.")
        self.assertEqual(estilo, "neutra")

    def test_acao_sensivel_executada_usa_tom_serio(self):
        texto, estilo = self.personality.compor(
            {"intent": "DESLIGAR_COMPUTADOR"},
            "Desligando o computador em 60 segundos. Diga 'cancelar desligamento' para interromper.",
        )
        self.assertEqual(estilo, "seria")
        self.assertIn("Rinaldo", texto)

    def test_erro_inesperado_do_ciclo_principal(self):
        texto, estilo = self.personality.erro_inesperado()
        self.assertEqual(estilo, "empatica")
        self.assertIn("Rinaldo", texto)

    def test_presenca_direto(self):
        texto, estilo = self.personality.presenca()
        self.assertEqual(texto, "Estou sim, Rinaldo. Sempre de prontidão.")
        self.assertEqual(estilo, "confirmacao")

    def test_compor_intent_presenca(self):
        texto, estilo = self.personality.compor({"intent": "PRESENCA"}, "Presença confirmada.")
        self.assertEqual(texto, "Estou sim, Rinaldo. Sempre de prontidão.")
        self.assertEqual(estilo, "confirmacao")


if __name__ == "__main__":
    unittest.main()
