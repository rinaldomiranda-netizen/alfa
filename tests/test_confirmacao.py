import unittest

from core.confirmacao import interpretar_resposta, pergunta_de_confirmacao


class TestConfirmacao(unittest.TestCase):

    def test_pergunta_de_confirmacao(self):
        self.assertEqual(
            pergunta_de_confirmacao("seu nome", "João da Silva"),
            "Só para confirmar: seu nome é João da Silva?",
        )

    def test_resposta_positiva(self):
        for frase in ["sim", "confirmo", "isso mesmo", "pode", "afirmativo"]:
            self.assertTrue(interpretar_resposta(frase), frase)

    def test_resposta_negativa(self):
        for frase in ["não", "cancela", "negativo", "esquece"]:
            self.assertFalse(interpretar_resposta(frase), frase)

    def test_resposta_ambigua_retorna_none(self):
        self.assertIsNone(interpretar_resposta("banana"))
        self.assertIsNone(interpretar_resposta("talvez amanhã"))


if __name__ == "__main__":
    unittest.main()
