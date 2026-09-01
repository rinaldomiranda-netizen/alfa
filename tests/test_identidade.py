import unittest

from core.identidade import contem_frase_autorizacao, eh_pessoa_conhecida


class TestPessoaConhecida(unittest.TestCase):

    def test_familiares_sao_reconhecidos(self):
        for nome in ["Rinaldo", "rinaldo", "Marlene", "Lucas Felipe", "Cassiano"]:
            self.assertTrue(eh_pessoa_conhecida(nome), nome)

    def test_nome_completo_contendo_familiar_e_reconhecido(self):
        self.assertTrue(eh_pessoa_conhecida("Rinaldo Miranda"))
        self.assertTrue(eh_pessoa_conhecida("Lucas Felipe Souza"))

    def test_visitante_nao_e_reconhecido(self):
        self.assertFalse(eh_pessoa_conhecida("Fulano de Tal"))
        self.assertFalse(eh_pessoa_conhecida("Maria"))

    def test_nome_vazio_nao_e_reconhecido(self):
        self.assertFalse(eh_pessoa_conhecida(""))
        self.assertFalse(eh_pessoa_conhecida(None))


class TestFraseDeAutorizacao(unittest.TestCase):

    def test_frase_exata_e_reconhecida(self):
        self.assertTrue(contem_frase_autorizacao("O Alpha autoriza."))
        self.assertTrue(contem_frase_autorizacao("o alpha autoriza"))

    def test_frase_dentro_de_uma_sentenca_maior(self):
        self.assertTrue(contem_frase_autorizacao("Pode seguir, o Alpha autoriza isso."))

    def test_frase_ausente(self):
        self.assertFalse(contem_frase_autorizacao("eu autorizo"))
        self.assertFalse(contem_frase_autorizacao("sim, pode"))
        self.assertFalse(contem_frase_autorizacao(""))
        self.assertFalse(contem_frase_autorizacao(None))

    def test_apenas_dizer_que_e_o_rinaldo_nao_basta(self):
        self.assertFalse(contem_frase_autorizacao("sou o Rinaldo, pode liberar"))


if __name__ == "__main__":
    unittest.main()
