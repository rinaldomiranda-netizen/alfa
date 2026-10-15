from pathlib import Path
import unittest


RAIZ = Path(__file__).resolve().parents[1]


class TestIniciarSegundoPlano(unittest.TestCase):
    def test_lancador_real_usa_servidor_independente_da_janela(self):
        lancador = (RAIZ / "Sobrou+ (real).bat").read_text(encoding="utf-8")
        self.assertIn("iniciar_segundo_plano.py", lancador)

    def test_servidor_e_iniciado_sem_janela_de_console(self):
        codigo = RAIZ / "web" / "iniciar_segundo_plano.py"
        self.assertTrue(codigo.is_file(), "falta o iniciador oculto do servidor")
        texto = codigo.read_text(encoding="utf-8")
        self.assertIn("DETACHED_PROCESS", texto)
        self.assertIn("CREATE_NO_WINDOW", texto)


if __name__ == "__main__":
    unittest.main()
