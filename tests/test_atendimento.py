"""
Testes do fluxo real de BETA_ATENDIMENTO (core/atendimento.py):
identificação da pessoa, roteiro genérico (herdado da etapa
anterior), navegação, autorização e foto.

Nenhum roteiro de pesquisa REAL é definido aqui — só roteiros de
exemplo mínimos para exercitar o MECANISMO.
"""

import unittest
from unittest.mock import MagicMock, patch

from core.atendimento import AtendimentoBeta, EstadoAtendimento

ROTEIRO_EXEMPLO = [
    {"campo": "Idade", "pergunta": "Qual é a sua idade?", "tipo": "texto"},
    {"campo": "Cidade", "pergunta": "Qual é a sua cidade?", "tipo": "texto", "confirmar": False},
]


def _sem_camera(**kwargs):
    """
    AtendimentoBeta sem depender de câmera real nem de localizar/abrir
    a pesquisa de verdade neste ambiente (isso chegaria a abrir uma
    janela de navegador real via core/pesquisa_app.py).
    """
    kwargs.setdefault("camera_module", None)
    kwargs.setdefault("pesquisa_app", None)
    return AtendimentoBeta(**kwargs)


def _identificar(atendimento, nome="João da Silva"):
    """Helper: passa pela fase de identificação com sucesso."""
    atendimento.processar_resposta(f"Meu nome é {nome}")
    return atendimento.processar_resposta("sim")


class TestIdentificacaoDaPessoa(unittest.TestCase):

    def setUp(self):
        self.atendimento = _sem_camera()

    @patch("core.atendimento.datetime")
    def test_saudacao_de_manha_pede_o_nome(self, mock_datetime):
        mock_datetime.now.return_value.hour = 9
        saudacao = self.atendimento.iniciar([])
        self.assertEqual(saudacao, "Bom dia! Seja bem-vindo. Com quem estou falando?")
        self.assertEqual(self.atendimento.estado, EstadoAtendimento.AGUARDANDO_NOME)

    @patch("core.atendimento.datetime")
    def test_saudacao_de_tarde(self, mock_datetime):
        mock_datetime.now.return_value.hour = 15
        saudacao = self.atendimento.iniciar([])
        self.assertEqual(saudacao, "Boa tarde! Seja bem-vindo. Com quem estou falando?")

    @patch("core.atendimento.datetime")
    def test_saudacao_de_noite(self, mock_datetime):
        mock_datetime.now.return_value.hour = 21
        saudacao = self.atendimento.iniciar([])
        self.assertEqual(saudacao, "Boa noite! Seja bem-vindo. Com quem estou falando?")

    def test_iniciar_proximo_usa_saudacao_diferente(self):
        saudacao = self.atendimento.iniciar_proximo([])
        self.assertEqual(saudacao, "Olá! Vamos começar um novo atendimento. Com quem estou falando?")

    def test_nome_extraido_de_frase_com_prefixo(self):
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        resultado = self.atendimento.processar_resposta("Meu nome é João da Silva")
        self.assertEqual(resultado["acao"], "confirmar")
        self.assertEqual(
            resultado["mensagem"], "Só para confirmar, estou falando com João da Silva?"
        )

    def test_nome_sem_prefixo_tambem_funciona(self):
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        resultado = self.atendimento.processar_resposta("João")
        self.assertIn("João", resultado["mensagem"])

    def test_confirmacao_positiva_avanca_para_o_roteiro_com_saudacao_pessoal(self):
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        resultado = _identificar(self.atendimento, "João da Silva")

        self.assertEqual(resultado["acao"], "proxima_pergunta")
        self.assertEqual(resultado["mensagem"], "Perfeito, Seu João. Vamos começar.")
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua idade?")
        self.assertEqual(self.atendimento.titulo_pessoa, "Seu João")
        self.assertEqual(self.atendimento.nome_pessoa, "João da Silva")

    def test_titulo_usa_dona_para_nome_feminino(self):
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        _identificar(self.atendimento, "Maria Souza")
        self.assertEqual(self.atendimento.titulo_pessoa, "Dona Maria")

    def test_titulo_usa_seu_para_nome_masculino(self):
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        _identificar(self.atendimento, "João da Silva")
        self.assertEqual(self.atendimento.titulo_pessoa, "Seu João")

    def test_confirmacao_negativa_pede_o_nome_de_novo(self):
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        self.atendimento.processar_resposta("João")
        resultado = self.atendimento.processar_resposta("não")

        self.assertEqual(resultado["acao"], "repetir_pergunta")
        self.assertEqual(
            resultado["mensagem"],
            "Desculpe, não consegui entender. Pode repetir seu nome, por favor?",
        )
        self.assertEqual(self.atendimento.estado, EstadoAtendimento.AGUARDANDO_NOME)

    def test_resposta_ambigua_a_confirmacao_do_nome_repete_a_pergunta(self):
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        self.atendimento.processar_resposta("João")
        resultado = self.atendimento.processar_resposta("talvez")

        self.assertEqual(resultado["acao"], "repetir_confirmacao")
        self.assertIn("João", resultado["mensagem"])
        self.assertEqual(self.atendimento.estado, EstadoAtendimento.CONFIRMANDO_NOME)

    def test_mensagem_nao_entendi_depende_do_estado(self):
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        self.assertIn("nome", self.atendimento.mensagem_nao_entendi().lower())

        _identificar(self.atendimento)
        self.assertNotIn("nome", self.atendimento.mensagem_nao_entendi().lower())

    def test_pessoa_conhecida_e_marcada_corretamente(self):
        # Roteiro não-vazio de propósito: com roteiro vazio o
        # atendimento já finaliza e limpa o contexto (nome,
        # pessoa_conhecida, etc.) na mesma chamada — ver
        # test_roteiro_vazio_apos_identificacao_finaliza_direto.
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        _identificar(self.atendimento, "Rinaldo")
        self.assertTrue(self.atendimento.pessoa_conhecida)

    def test_visitante_nao_e_pessoa_conhecida(self):
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        _identificar(self.atendimento, "Fulano de Tal")
        self.assertFalse(self.atendimento.pessoa_conhecida)

    def test_roteiro_vazio_apos_identificacao_finaliza_direto(self):
        self.atendimento.iniciar([])
        resultado = _identificar(self.atendimento, "João")

        self.assertEqual(resultado["acao"], "finalizado")
        self.assertEqual(
            resultado["mensagem"], "Pronto, Seu João. Seu atendimento foi concluído. Muito obrigado."
        )
        self.assertFalse(self.atendimento.esta_ativo())


class TestRoteiroAposIdentificacao(unittest.TestCase):

    def setUp(self):
        self.atendimento = _sem_camera()
        self.atendimento.iniciar(ROTEIRO_EXEMPLO)
        _identificar(self.atendimento, "João da Silva")

    def test_confirmacao_de_campo_usa_template_customizado(self):
        roteiro = [
            {
                "campo": "Idade",
                "pergunta": "Qual é a sua idade?",
                "tipo": "texto",
                "confirmar_template": "Você tem {valor} anos, correto?",
            }
        ]
        atendimento = _sem_camera()
        atendimento.iniciar(roteiro)
        _identificar(atendimento, "Maria")

        resultado = atendimento.processar_resposta("35")
        self.assertEqual(resultado["mensagem"], "Você tem 35 anos, correto?")

    def test_fluxo_completo_ate_a_conclusao(self):
        resultado = self.atendimento.processar_resposta("35")
        self.assertEqual(resultado["acao"], "confirmar")

        resultado = self.atendimento.processar_resposta("sim")
        self.assertEqual(resultado["acao"], "proxima_pergunta")
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua cidade?")

        # "Cidade" tem confirmar=False: registra direto.
        resultado = self.atendimento.processar_resposta("Recife")

        self.assertEqual(resultado["acao"], "finalizado")
        self.assertEqual(
            resultado["mensagem"], "Pronto, Seu João. Seu atendimento foi concluído. Muito obrigado."
        )
        self.assertEqual(resultado["dados"], {"Idade": "35", "Cidade": "Recife"})

    def test_negar_confirmacao_de_campo_repete_a_pergunta_original(self):
        self.atendimento.processar_resposta("35")
        resultado = self.atendimento.processar_resposta("não")

        self.assertEqual(resultado["acao"], "repetir_pergunta")
        self.assertEqual(resultado["mensagem"], "Qual é a sua idade?")
        self.assertNotIn("Idade", self.atendimento.respostas)


class TestNavegacao(unittest.TestCase):

    def test_passo_de_navegacao_e_executado_sem_perguntar_nada(self):
        form_filler = MagicMock()
        form_filler.avancar.return_value = "Avancei (Próximo)."

        roteiro = [
            {"campo": "Idade", "pergunta": "Qual é a sua idade?", "tipo": "texto", "confirmar": False},
            {"tipo": "navegacao", "acao": "avancar"},
            {"campo": "Cidade", "pergunta": "Qual é a sua cidade?", "tipo": "texto", "confirmar": False},
        ]

        atendimento = _sem_camera(form_filler=form_filler)
        atendimento.iniciar(roteiro)
        _identificar(atendimento, "Ana")

        resultado = atendimento.processar_resposta("30")

        form_filler.avancar.assert_called_once()
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua cidade?")

    def test_navegacao_no_inicio_do_roteiro_e_executada_antes_da_primeira_pergunta(self):
        form_filler = MagicMock()
        roteiro = [
            {"tipo": "navegacao", "acao": "confirmar"},
            {"campo": "Idade", "pergunta": "Qual é a sua idade?", "tipo": "texto"},
        ]

        atendimento = _sem_camera(form_filler=form_filler)
        atendimento.iniciar(roteiro)
        resultado = _identificar(atendimento, "Ana")

        form_filler.confirmar.assert_called_once()
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua idade?")

    def test_navegacao_sem_form_filler_nao_quebra(self):
        roteiro = [
            {"tipo": "navegacao", "acao": "avancar"},
            {"campo": "Idade", "pergunta": "Qual é a sua idade?", "tipo": "texto"},
        ]
        atendimento = _sem_camera()
        atendimento.iniciar(roteiro)
        resultado = _identificar(atendimento, "Ana")
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua idade?")


class TestAutorizacao(unittest.TestCase):

    def _roteiro_com_autorizacao(self):
        return [
            {
                "campo": "Renda familiar",
                "pergunta": "Qual é a sua renda familiar?",
                "tipo": "texto",
                "confirmar": False,
                "requer_autorizacao": True,
            },
            {"campo": "Cidade", "pergunta": "Qual é a sua cidade?", "tipo": "texto", "confirmar": False},
        ]

    def test_visitante_sem_frase_de_autorizacao_e_bloqueado(self):
        atendimento = _sem_camera()
        atendimento.iniciar(self._roteiro_com_autorizacao())
        resultado = _identificar(atendimento, "Fulano de Tal")

        self.assertEqual(atendimento.estado, EstadoAtendimento.AGUARDANDO_AUTORIZACAO)
        self.assertIn("autorização", resultado["proxima_pergunta"].lower())

    def test_visitante_sem_a_frase_correta_pula_a_pergunta(self):
        atendimento = _sem_camera()
        atendimento.iniciar(self._roteiro_com_autorizacao())
        _identificar(atendimento, "Fulano de Tal")

        resultado = atendimento.processar_resposta("eu autorizo")

        self.assertEqual(resultado["mensagem"], "Sem autorização, vou pular essa pergunta.")
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua cidade?")
        self.assertNotIn("Renda familiar", atendimento.respostas)

    def test_visitante_com_a_frase_de_autorizacao_correta_prossegue(self):
        atendimento = _sem_camera()
        atendimento.iniciar(self._roteiro_com_autorizacao())
        _identificar(atendimento, "Fulano de Tal")

        resultado = atendimento.processar_resposta("O Alpha autoriza.")

        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua renda familiar?")
        self.assertTrue(atendimento.frase_autorizacao_ouvida)

    def test_pessoa_conhecida_nao_precisa_da_frase(self):
        atendimento = _sem_camera()
        atendimento.iniciar(self._roteiro_com_autorizacao())
        resultado = _identificar(atendimento, "Rinaldo")

        self.assertEqual(atendimento.estado, EstadoAtendimento.PERGUNTANDO)
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua renda familiar?")

    def test_dizer_sou_rinaldo_nao_concede_autorizacao_sozinho(self):
        # Alegar ser o Rinaldo (via nome) sem a frase de autorização
        # NÃO deve liberar o passo sensível.
        atendimento = _sem_camera()
        atendimento.iniciar(self._roteiro_com_autorizacao())
        _identificar(atendimento, "Fulano de Tal")

        resultado = atendimento.processar_resposta("Sou o Rinaldo, pode liberar")

        self.assertEqual(resultado["mensagem"], "Sem autorização, vou pular essa pergunta.")


class TestFluxoDeFoto(unittest.TestCase):

    def _roteiro_com_foto(self):
        return [
            {"tipo": "foto"},
            {"campo": "Cidade", "pergunta": "Qual é a sua cidade?", "tipo": "texto", "confirmar": False},
        ]

    def test_pergunta_de_consentimento_usa_o_primeiro_nome(self):
        atendimento = _sem_camera()
        atendimento.iniciar(self._roteiro_com_foto())
        resultado = _identificar(atendimento, "João da Silva")

        self.assertEqual(atendimento.estado, EstadoAtendimento.AGUARDANDO_CONSENTIMENTO_FOTO)
        self.assertEqual(
            resultado["proxima_pergunta"],
            "João, preciso tirar uma foto para registrar seu atendimento. Posso tirar?",
        )

    def test_consentimento_negado_pula_a_foto(self):
        atendimento = _sem_camera()
        atendimento.iniciar(self._roteiro_com_foto())
        _identificar(atendimento, "João")

        resultado = atendimento.processar_resposta("não")

        self.assertEqual(resultado["mensagem"], "Sem problema, vamos seguir sem a foto.")
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua cidade?")

    def test_consentimento_concedido_captura_mostra_e_confirma(self):
        camera_module = MagicMock()
        sessao_mock = MagicMock()
        camera_module.SessaoCamera.return_value = sessao_mock

        atendimento = AtendimentoBeta(camera_module=camera_module, pesquisa_app=None)
        atendimento.iniciar(self._roteiro_com_foto())
        _identificar(atendimento, "João")

        resultado = atendimento.processar_resposta("sim")

        sessao_mock.registrar_consentimento.assert_called_once_with(True)
        sessao_mock.capturar_foto.assert_called_once()
        sessao_mock.mostrar_previa.assert_called_once()
        self.assertEqual(atendimento.estado, EstadoAtendimento.AGUARDANDO_CONFIRMACAO_FOTO)
        self.assertEqual(resultado["acao"], "confirmar")
        self.assertIn("boa foto", resultado["mensagem"].lower())

        id_atendimento = atendimento.atendimento_id
        resultado_final = atendimento.processar_resposta("sim, ficou boa")

        sessao_mock.confirmar.assert_called_once_with(True)
        sessao_mock.associar_ao_atendimento.assert_called_once_with(id_atendimento)
        self.assertEqual(resultado_final["mensagem"], "Foto registrada.")
        self.assertEqual(resultado_final["proxima_pergunta"], "Qual é a sua cidade?")

    def test_recusar_a_foto_tenta_de_novo_ate_o_limite(self):
        camera_module = MagicMock()
        camera_module.SessaoCamera.side_effect = lambda: MagicMock()

        atendimento = AtendimentoBeta(camera_module=camera_module, pesquisa_app=None)
        atendimento.iniciar(self._roteiro_com_foto())
        _identificar(atendimento, "João")

        atendimento.processar_resposta("sim")  # concede consentimento, tira a 1ª foto
        for _ in range(3):
            resultado = atendimento.processar_resposta("não, tire de novo")

        # Depois de MAX_TENTATIVAS_FOTO, desiste e segue o roteiro.
        self.assertEqual(resultado["mensagem"], "Sem problema, vamos seguir sem a foto.")
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua cidade?")

    def test_camera_indisponivel_segue_sem_foto(self):
        atendimento = _sem_camera(camera_module=None)
        atendimento.iniciar(self._roteiro_com_foto())
        _identificar(atendimento, "João")

        resultado = atendimento.processar_resposta("sim")

        self.assertIn("não consegui acessar a câmera", resultado["mensagem"].lower())
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua cidade?")

    def test_falha_na_captura_segue_sem_foto(self):
        camera_module = MagicMock()
        sessao_mock = MagicMock()
        sessao_mock.capturar_foto.side_effect = RuntimeError("sem câmera conectada")
        camera_module.SessaoCamera.return_value = sessao_mock

        atendimento = AtendimentoBeta(camera_module=camera_module, pesquisa_app=None)
        atendimento.iniciar(self._roteiro_com_foto())
        _identificar(atendimento, "João")

        resultado = atendimento.processar_resposta("sim")

        self.assertIn("não consegui tirar a foto", resultado["mensagem"].lower())
        self.assertEqual(resultado["proxima_pergunta"], "Qual é a sua cidade?")


class TestCicloDeVidaELimpezaDeContexto(unittest.TestCase):

    def test_limpar_estado_reseta_identidade_e_foto(self):
        atendimento = _sem_camera()
        atendimento.iniciar(ROTEIRO_EXEMPLO)
        _identificar(atendimento, "João da Silva")

        atendimento.limpar_estado()

        self.assertEqual(atendimento.estado, EstadoAtendimento.INATIVO)
        self.assertIsNone(atendimento.nome_pessoa)
        self.assertIsNone(atendimento.titulo_pessoa)
        self.assertFalse(atendimento.pessoa_conhecida)
        self.assertFalse(atendimento.frase_autorizacao_ouvida)
        self.assertIsNone(atendimento.sessao_camera)
        self.assertEqual(atendimento.respostas, {})

    def test_dados_da_pessoa_anterior_nunca_aparecem_no_proximo_atendimento(self):
        atendimento = _sem_camera()
        atendimento.iniciar(ROTEIRO_EXEMPLO)
        _identificar(atendimento, "João da Silva")
        atendimento.processar_resposta("35")
        atendimento.processar_resposta("sim")
        atendimento.processar_resposta("Recife")  # finaliza

        atendimento.iniciar_proximo(ROTEIRO_EXEMPLO)

        self.assertIsNone(atendimento.nome_pessoa)
        self.assertEqual(atendimento.respostas, {})
        self.assertEqual(atendimento.estado, EstadoAtendimento.AGUARDANDO_NOME)

    def test_cada_atendimento_recebe_um_id_novo(self):
        atendimento = _sem_camera()
        atendimento.iniciar([])
        id1 = atendimento.atendimento_id
        atendimento.iniciar_proximo([])
        id2 = atendimento.atendimento_id

        self.assertIsNotNone(id1)
        self.assertIsNotNone(id2)
        self.assertNotEqual(id1, id2)


class TestIdentificarTela(unittest.TestCase):

    def test_sem_vision_module_nao_falha(self):
        atendimento = _sem_camera()
        self.assertIsNone(atendimento.identificar_tela())

    def test_usa_timeout_curto_best_effort(self):
        vision_mock = MagicMock()
        vision_mock.analisar_tela.return_value = "Formulário de cadastro aberto."
        atendimento = _sem_camera(vision_module=vision_mock)

        resultado = atendimento.identificar_tela()

        vision_mock.analisar_tela.assert_called_once_with(timeout=4)
        self.assertEqual(resultado, "Formulário de cadastro aberto.")

    def test_falha_na_visao_nao_impede_identificacao(self):
        vision_mock = MagicMock()
        vision_mock.analisar_tela.side_effect = RuntimeError("sem tela")
        atendimento = _sem_camera(vision_module=vision_mock)
        atendimento.iniciar(ROTEIRO_EXEMPLO)
        self.assertTrue(atendimento.esta_ativo())


if __name__ == "__main__":
    unittest.main()
