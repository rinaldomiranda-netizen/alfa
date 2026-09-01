import unittest

from core.normalizer import normalize


class TestNormalizer(unittest.TestCase):

    def test_minusculas_e_acentos(self):
        self.assertEqual(normalize("MOVA O MOUSE PARA ESQUERDA"), "mova o mouse para esquerda")
        self.assertEqual(normalize("posição do mouse"), "posicao do mouse")

    def test_pontuacao_e_espacos_duplicados(self):
        self.assertEqual(normalize("abra,   a calculadora!!!"), "abra a calculadora")

    def test_string_vazia(self):
        self.assertEqual(normalize(""), "")
        self.assertEqual(normalize(None), "")

    # Casos de correção de domínio exigidos explicitamente.
    def test_ovo_ao_maus(self):
        self.assertEqual(normalize("ovo ao maus"), "mover mouse")

    def test_ovo_ao_mouse(self):
        self.assertEqual(normalize("ovo ao mouse"), "mover mouse")

    def test_mova_o_maus(self):
        self.assertEqual(normalize("mova o maus"), "mover mouse")

    def test_mexa_o_mause(self):
        self.assertEqual(normalize("mexa o mause"), "mexa o mouse")

    def test_ovo_ao_maus_com_direcao_preservada(self):
        self.assertEqual(normalize("ovo ao maus para direita"), "mover mouse para direita")

    def test_nao_corrompe_palavra_legitima_fora_de_contexto(self):
        # "maus" (plural de "mau") sem verbo de movimento não deve virar "mouse".
        self.assertEqual(normalize("os maus sempre voltam"), "os maus sempre voltam")

    def test_arraste_o_mause(self):
        self.assertEqual(normalize("arraste o mause para baixo"), "arraste o mouse para baixo")

    def test_vocativo_beta_no_inicio_e_removido(self):
        self.assertEqual(normalize("Beta, abra o navegador"), "abra o navegador")
        self.assertEqual(normalize("beta mova o mouse para direita"), "mova o mouse para direita")

    def test_vocativo_alfa_no_inicio_e_removido_por_compatibilidade(self):
        self.assertEqual(normalize("Alfa, abra a calculadora"), "abra a calculadora")

    def test_beta_como_objeto_da_frase_nao_e_removido(self):
        # "beta"/"alfa" só é removido como vocativo no INÍCIO da frase;
        # como objeto (ex.: comando de encerrar), deve ser preservado.
        self.assertEqual(normalize("desligue a beta"), "desligue a beta")
        self.assertEqual(normalize("encerre o alfa"), "encerre o alfa")


if __name__ == "__main__":
    unittest.main()
