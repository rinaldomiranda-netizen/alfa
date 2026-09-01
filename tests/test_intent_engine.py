"""
Testes do interpretador de comandos (NLU).

Cada caso documenta: frase -> intenção esperada -> parâmetros
esperados. Cobre os exemplos exigidos nas seções 4 e 9 da
especificação (comandos de mouse em linguagem natural, sem exigir a
palavra "mouse" em toda frase, mais clique/abrir/fechar/scroll).
"""

import unittest

from core.intent_engine import IntentEngine

# frase, intent esperado, parâmetros esperados (subconjunto verificado)
CASOS = [
    # --- Seção 9: casos explicitamente exigidos -----------------
    ("ovo ao maus", "MOVER_MOUSE", {"direcao": None}),
    ("ovo ao maus para direita", "MOVER_MOUSE", {"direcao": "direita"}),
    ("mova mais para esquerda", "MOVER_MOUSE", {"direcao": "esquerda"}),
    ("mova o mouse para esquerda", "MOVER_MOUSE", {"direcao": "esquerda"}),
    ("mova o ponteiro para cima", "MOVER_MOUSE", {"direcao": "cima"}),
    ("arraste para baixo", "ARRASTAR_MOUSE", {"direcao": "baixo"}),
    ("dê dois cliques", "CLIQUE", {"botao": "duplo"}),
    ("abra o navegador", "ABRIR", {"programa": "navegador"}),
    ("role a página para baixo", "SCROLL", {"direcao": "baixo"}),

    # --- Seção 4: comandos de mouse em linguagem natural --------
    ("mova o mouse para a esquerda", "MOVER_MOUSE", {"direcao": "esquerda"}),
    ("mova para a direita", "MOVER_MOUSE", {"direcao": "direita"}),
    ("leve o ponteiro para cima", "MOVER_MOUSE", {"direcao": "cima"}),
    ("leve o ponteiro para baixo", "MOVER_MOUSE", {"direcao": "baixo"}),
    ("arraste o mouse para a direita", "ARRASTAR_MOUSE", {"direcao": "direita"}),
    ("mexa o mouse para esquerda", "MOVER_MOUSE", {"direcao": "esquerda"}),
    ("mova o mouse para cima", "MOVER_MOUSE", {"direcao": "cima"}),

    # --- Variações adicionais (erros comuns de STT) --------------
    ("mexa o mause para direita", "MOVER_MOUSE", {"direcao": "direita"}),
    ("coloque o mouse no centro", "MOVER_MOUSE", {"direcao": "centro"}),
    ("suba o mouse", "MOVER_MOUSE", {}),
    ("onde está o mouse", "POSICAO_MOUSE", {}),
    ("qual a posição do mouse", "POSICAO_MOUSE", {}),
    ("clique direito", "CLIQUE", {"botao": "direito"}),
    ("clique duas vezes", "CLIQUE", {"botao": "duplo"}),
    ("clique", "CLIQUE", {"botao": "esquerdo"}),
    ("copie isso", "COPIAR", {}),
    ("cole o texto", "COLAR", {}),
    ("desfazer", "DESFAZER", {}),
    ("selecione tudo", "SELECIONAR_TUDO", {}),
    ("pressione enter", "ENTER", {}),
    ("aperte esc", "ESC", {}),
    ("feche a calculadora", "FECHAR", {"programa": "calculadora"}),
    ("abra a calculadora", "ABRIR", {"programa": "calculadora"}),
    ("role a página para cima", "SCROLL", {"direcao": "cima"}),
    ("saia", "SAIR", {}),
    ("blablabla xpto inexistente", "DESCONHECIDO", {}),

    # --- Novos comandos: teclado, janelas, volume, energia -------
    ("recorte isso", "RECORTAR", {}),
    ("refazer", "REFAZER", {}),
    ("pressione tab", "TAB", {}),
    ("apague isso", "BACKSPACE", {}),
    ("minimizar a janela", "MINIMIZAR_JANELA", {}),
    ("maximizar a janela", "MAXIMIZAR_JANELA", {}),
    ("feche a janela", "FECHAR_JANELA", {}),
    ("alternar janela", "ALTERNAR_JANELA", {}),
    ("mostrar área de trabalho", "MOSTRAR_AREA_TRABALHO", {}),
    ("aumentar o volume", "VOLUME_AUMENTAR", {}),
    ("diminuir o volume", "VOLUME_DIMINUIR", {}),
    ("modo mudo", "VOLUME_MUDO", {}),
    ("desligar o computador", "DESLIGAR_COMPUTADOR", {}),
    ("reiniciar o computador", "REINICIAR_COMPUTADOR", {}),
    ("cancelar desligamento", "CANCELAR_DESLIGAMENTO", {}),
    ("olhe minha tela", "VISUALIZAR", {}),
    ("veja pela câmera", "CAMERA", {}),
    ("digite olá mundo", "DIGITAR", {}),

    # --- Controle estendido do computador -------------------------
    ("pressione delete", "PRESSIONAR_TECLA", {"tecla": "delete"}),
    ("aperte espaço", "PRESSIONAR_TECLA", {"tecla": "space"}),
    ("atalho salvar", "ATALHO", {"nome": "salvar", "teclas": ("ctrl", "s")}),
    ("abra a pasta downloads", "ABRIR_PASTA", {"nome": "downloads"}),
    ("abra o arquivo relatorio", "ABRIR_ARQUIVO", {"nome": "relatorio"}),

    # --- Ação orientada por elementos -------------------------------
    ("clique no botão salvar", "CLICAR_ELEMENTO", {"nome": "salvar"}),
    ("marque a caixa concordo", "MARCAR_CAIXA", {"campo": "concordo", "marcar": True}),
    ("desmarque a caixa concordo", "MARCAR_CAIXA", {"campo": "concordo", "marcar": False}),
    ("selecione masculino no campo gênero", "SELECIONAR_OPCAO", {"opcao": "masculino"}),
    ("onde está o botão salvar", "LOCALIZAR", {"alvo": "botao salvar"}),

    # --- Modo de atendimento -----------------------------------------
    ("iniciar atendimento", "INICIAR_ATENDIMENTO", {}),
    ("encerrar atendimento", "ENCERRAR_ATENDIMENTO", {}),
]


class TestIntentEngine(unittest.TestCase):

    def setUp(self):
        self.engine = IntentEngine()

    def test_tabela_de_casos(self):
        falhas = []

        for frase, intent_esperado, params_esperados in CASOS:
            resultado = self.engine.interpretar(frase)

            if resultado.get("intent") != intent_esperado:
                falhas.append(
                    f"FRASE={frase!r} esperado intent={intent_esperado} "
                    f"obtido={resultado.get('intent')} (resultado={resultado})"
                )
                continue

            for chave, valor_esperado in params_esperados.items():
                valor_obtido = resultado.get(chave)
                if valor_obtido != valor_esperado:
                    falhas.append(
                        f"FRASE={frase!r} esperado {chave}={valor_esperado!r} "
                        f"obtido={valor_obtido!r} (resultado={resultado})"
                    )

        if falhas:
            self.fail("\n" + "\n".join(falhas))

    def test_quantidade_minima_de_casos(self):
        self.assertGreaterEqual(len(CASOS), 20)

    def test_contexto_mouse_mais_para_esquerda_apos_comando_anterior(self):
        # Fala anterior estabelece o alvo "mouse".
        self.engine.interpretar("mova o mouse para a direita")
        resultado = self.engine.interpretar("mais para esquerda")
        self.assertEqual(resultado["intent"], "MOVER_MOUSE")
        self.assertEqual(resultado["direcao"], "esquerda")

    def test_digitar_preserva_maiusculas_e_acentos_do_texto_original(self):
        texto_original = "Digite Olá Mundo!"
        resultado = self.engine.interpretar(
            self.engine.normalizar(texto_original),
            texto_original=texto_original,
        )
        self.assertEqual(resultado["intent"], "DIGITAR")
        self.assertEqual(resultado["texto"], "Olá Mundo!")

    def test_digite_sair_nao_encerra_o_alfa(self):
        resultado = self.engine.interpretar("digite sair", texto_original="digite sair")
        self.assertEqual(resultado["intent"], "DIGITAR")
        self.assertEqual(resultado["texto"], "sair")

    def test_fechar_calculadora_nao_e_confundido_com_fechar_janela(self):
        resultado = self.engine.interpretar("feche a calculadora")
        self.assertEqual(resultado["intent"], "FECHAR")
        self.assertEqual(resultado["programa"], "calculadora")

    def test_desligar_alfa_nao_e_confundido_com_desligar_computador(self):
        resultado = self.engine.interpretar("desligue o alfa")
        self.assertEqual(resultado["intent"], "SAIR")

    def test_desligar_beta_tambem_encerra_o_assistente(self):
        resultado = self.engine.interpretar("desligue a beta")
        self.assertEqual(resultado["intent"], "SAIR")

    def test_chamado_beta_no_inicio_nao_atrapalha_o_comando(self):
        resultado = self.engine.interpretar("Beta, abra o navegador")
        self.assertEqual(resultado["intent"], "ABRIR")
        self.assertEqual(resultado["programa"], "navegador")

    def test_chamado_beta_com_comando_de_mouse(self):
        resultado = self.engine.interpretar("beta mova o mouse para a direita")
        self.assertEqual(resultado["intent"], "MOVER_MOUSE")
        self.assertEqual(resultado["direcao"], "direita")

    def test_pergunta_de_presenca(self):
        resultado = self.engine.interpretar("Beta, você está aí?")
        self.assertEqual(resultado["intent"], "PRESENCA")


if __name__ == "__main__":
    unittest.main()
