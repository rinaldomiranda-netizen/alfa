"""
Testes do armazenamento local de atendimentos (memory/memory.py).

Sempre redireciona PASTA_ATENDIMENTOS para um diretório temporário —
nunca cria/apaga nada na pasta real memory/atendimentos/ do projeto.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from memory import memory


class TestMemory(unittest.TestCase):

    def test_salvar_e_carregar_atendimento(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(memory, "PASTA_ATENDIMENTOS", tmp):
                atendimento_id = memory.novo_id_atendimento()
                memory.salvar_atendimento(atendimento_id, {"Nome completo": "Maria"})

                carregado = memory.carregar_atendimento(atendimento_id)

                self.assertIsNotNone(carregado)
                self.assertEqual(carregado["id"], atendimento_id)
                self.assertEqual(carregado["dados"], {"Nome completo": "Maria"})

    def test_carregar_atendimento_inexistente_retorna_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(memory, "PASTA_ATENDIMENTOS", tmp):
                self.assertIsNone(memory.carregar_atendimento("nao-existe"))

    def test_limpar_atendimento_remove_json_e_foto(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(memory, "PASTA_ATENDIMENTOS", tmp):
                atendimento_id = memory.novo_id_atendimento()
                memory.salvar_atendimento(atendimento_id, {"Nome": "Ana"})

                caminho_foto = os.path.join(tmp, f"{atendimento_id}_foto.jpg")
                with open(caminho_foto, "wb") as arquivo:
                    arquivo.write(b"fake-jpg")

                removido = memory.limpar_atendimento(atendimento_id)

                self.assertTrue(removido)
                self.assertIsNone(memory.carregar_atendimento(atendimento_id))
                self.assertFalse(os.path.exists(caminho_foto))

    def test_listar_atendimentos(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(memory, "PASTA_ATENDIMENTOS", tmp):
                id1 = memory.novo_id_atendimento()
                memory.salvar_atendimento(id1, {"a": 1})

                self.assertIn(id1, memory.listar_atendimentos())

    def test_listar_atendimentos_pasta_inexistente_retorna_vazio(self):
        with patch.object(memory, "PASTA_ATENDIMENTOS", "/caminho/que/nao/existe/nunca"):
            self.assertEqual(memory.listar_atendimentos(), [])


if __name__ == "__main__":
    unittest.main()
