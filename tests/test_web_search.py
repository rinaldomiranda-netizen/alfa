import unittest
from unittest.mock import MagicMock, patch

from core import web_search


HTML = """
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fnoticia">Título da notícia</a>
  <a class="result__snippet">Um trecho de resumo <b>com destaque</b> e mais texto.</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.org/fonte">Outra fonte</a>
  <a class="result__snippet">Segundo resumo.</a>
</div>
"""


class TestPesquisaWeb(unittest.TestCase):
    @patch("core.web_search.urlopen")
    def test_extrai_titulo_resumo_e_url_direta(self, mock_urlopen):
        resposta = MagicMock()
        resposta.status = 200
        resposta.headers.get_content_charset.return_value = "utf-8"
        resposta.read.return_value = HTML.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = resposta

        sucesso, mensagem = web_search.pesquisar("notícia de teste")

        self.assertTrue(sucesso)
        self.assertIn("Título da notícia", mensagem)
        self.assertIn("Um trecho de resumo com destaque e mais texto.", mensagem)
        self.assertIn("https://example.com/noticia", mensagem)
        self.assertNotIn("duckduckgo.com/l/", mensagem)
        mock_urlopen.assert_called_once()

    @patch("core.web_search.urlopen")
    def test_limita_quantidade_de_resultados(self, mock_urlopen):
        resposta = MagicMock()
        resposta.status = 200
        resposta.headers.get_content_charset.return_value = "utf-8"
        resposta.read.return_value = HTML.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = resposta

        sucesso, mensagem = web_search.pesquisar("notícia de teste", limite=1)

        self.assertTrue(sucesso)
        self.assertIn("Título da notícia", mensagem)
        self.assertNotIn("Outra fonte", mensagem)

    @patch("core.web_search.urlopen")
    def test_busca_vazia_nao_acessa_a_internet(self, mock_urlopen):
        sucesso, mensagem = web_search.pesquisar("   ")

        self.assertFalse(sucesso)
        self.assertIn("Não entendi", mensagem)
        mock_urlopen.assert_not_called()

    @patch("core.web_search.urlopen", side_effect=OSError("offline"))
    def test_falha_de_rede_retorna_mensagem_honesta(self, mock_urlopen):
        sucesso, mensagem = web_search.pesquisar("informação atual")

        self.assertFalse(sucesso)
        self.assertIn("não consegui pesquisar", mensagem.lower())

    @patch("core.web_search.urlopen")
    def test_html_sem_resultados_nao_inventa_resposta(self, mock_urlopen):
        resposta = MagicMock()
        resposta.status = 200
        resposta.headers.get_content_charset.return_value = "utf-8"
        resposta.read.return_value = b"<html><body>sem resultados</body></html>"
        mock_urlopen.return_value.__enter__.return_value = resposta

        sucesso, mensagem = web_search.pesquisar("assunto inexistente")

        self.assertFalse(sucesso)
        self.assertIn("não retornou resultados", mensagem.lower())


if __name__ == "__main__":
    unittest.main()
