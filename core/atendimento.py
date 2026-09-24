"""
BETA_ATENDIMENTO — fluxo real de atendimento presencial.

Protocolo completo (o roteiro de PERGUNTAS específicas continua sendo
fornecido de fora — um módulo de pesquisa futuro —, mas o PROTOCOLO
em volta dele é responsabilidade deste módulo):

    saudação por horário
    -> "com quem estou falando?"
    -> (se não entender) pede para repetir o nome
    -> confirma o nome ouvido
    -> "Perfeito, Seu <Nome>. Vamos começar."
    -> identificar tela
    -> roteiro: perguntar -> ouvir -> confirmar -> preencher -> avançar -> repetir
       (inclui, quando o passo pedir: consentimento de foto -> capturar
       -> mostrar prévia -> confirmar/refazer; e, quando o passo exigir
       autorização, checar a frase de autorização do Rinaldo)
    -> "Pronto, Seu <Nome>. Seu atendimento foi concluído. Muito obrigado."
    -> limpa TODO o contexto da pessoa (nunca vaza para o próximo)
    -> prepara automaticamente o próximo atendimento:
       "Olá! Vamos começar um novo atendimento. Com quem estou falando?"

Um "passo" de roteiro é um dict:
    {
        "campo": "Nome completo",           # rótulo do campo na tela
        "automation_id": "rmdInterviewName", # AutomationId real do elemento (opcional, mas preferido)
        "pergunta": "Qual é o seu nome completo?",  # ou None para perguntar dinamicamente
        "tipo": "texto",                     # "texto" | "opcao" | "opcao_botao" | "checkbox" | "foto"
        "opcoes": [...],                     # (tipo "opcao_botao") rótulos REAIS já conhecidos
        "confirmar": True,                   # pede confirmação antes de preencher?
        "confirmar_template": None,           # frase natural customizada ("Você tem {valor} anos?")
        "obrigatorio": False,                 # se True, um pedido de "pular" é recusado
        "requer_autorizacao": False,         # só visitantes desconhecidos + sem a frase pulam
        "pergunta_consentimento": None,       # (tipo "foto") texto customizado do pedido
    }
    ou um passo de navegação pura, sem pergunta nenhuma:
    {"tipo": "navegacao", "acao": "avancar"}      # "avancar" | "voltar" | "confirmar"
    {"tipo": "navegacao", "nome": "Registrar entrevista"}  # clica um botão por nome real

Quando `"pergunta"` é None e o tipo é "opcao", a pergunta é montada
dinamicamente lendo as opções REAIS do elemento na tela (nunca uma
lista inventada) — ver computer/form_filler.py:listar_opcoes(). Para
"opcao_botao" (grupo de botões, não um <select>), as opções vêm do
próprio roteiro em `"opcoes"` porque são rótulos fixos já conhecidos
do código-fonte da tela (ver core/roteiro_pesquisa.py).

Depois de preencher um campo de texto, o valor é verificado lendo o
elemento de volta (computer/form_filler.py); se a verificação falhar,
tenta mais uma vez antes de avisar a dificuldade — nunca avança
fingindo sucesso.

Nenhum roteiro de pesquisa é INVENTADO aqui — o conteúdo real vem de
core/roteiro_pesquisa.py (a tela "Nova entrevista" de verdade) ou de
outro módulo futuro; este arquivo só sabe executar o PROTOCOLO.
"""

import enum
import re
from datetime import datetime

try:
    from computer.form_filler import FalhaDeVerificacao
except Exception:
    # O protocolo também roda em servidor Linux (web). A automação
    # Windows só é necessária quando um FormFiller real é injetado.
    class FalhaDeVerificacao(Exception):
        pass
from core import identidade
from core.confirmacao import eh_pedido_de_pular, interpretar_resposta, pergunta_de_confirmacao
from memory import memory

MAX_TENTATIVAS_PREENCHIMENTO = 2

MENSAGEM_NAO_ENTENDI_NOME = "Desculpe, não consegui entender. Pode repetir seu nome, por favor?"
MENSAGEM_NAO_ENTENDI_GENERICA = "Desculpe, não consegui entender. Pode repetir para mim?"
SAUDACAO_PROXIMO_ATENDIMENTO = "Olá! Vamos começar um novo atendimento. Com quem estou falando?"

MAX_TENTATIVAS_FOTO = 3

# Confirmações curtas e naturais faladas depois de um preenchimento
# bem-sucedido — evita soar como formulário ("Preenchi 'X' com 'Y'.")
# a cada resposta.
CONFIRMACOES_NATURAIS = ["Perfeito.", "Entendido.", "Show, anotado.", "Certo, já registrei."]

_CAMERA_NAO_INFORMADA = object()
_PESQUISA_APP_NAO_INFORMADO = object()

_PREFIXOS_NOME = re.compile(
    r"^\s*(?:meu nome (?:e|é)|me chamo|eu me chamo|pode me chamar de|"
    r"eu sou o|eu sou a|eu sou|sou o|sou a|sou)\s+",
    re.IGNORECASE,
)


class EstadoAtendimento(enum.Enum):
    INATIVO = "inativo"
    AGUARDANDO_NOME = "aguardando_nome"
    CONFIRMANDO_NOME = "confirmando_nome"
    PERGUNTANDO = "perguntando"
    AGUARDANDO_CONFIRMACAO = "aguardando_confirmacao"
    AGUARDANDO_AUTORIZACAO = "aguardando_autorizacao"
    AGUARDANDO_CONSENTIMENTO_FOTO = "aguardando_consentimento_foto"
    AGUARDANDO_CONFIRMACAO_FOTO = "aguardando_confirmacao_foto"
    CONCLUIDO = "concluido"


class AtendimentoBeta:
    """Máquina de estados do modo de atendimento presencial da BETA."""

    def __init__(
        self,
        form_filler=None,
        vision_module=None,
        camera_module=_CAMERA_NAO_INFORMADA,
        pesquisa_app=_PESQUISA_APP_NAO_INFORMADO,
    ):
        self.form_filler = form_filler
        self.vision_module = vision_module

        # Diferencia "não informado" (tenta importar o módulo real de
        # câmera) de "informado como None" (desliga a câmera de
        # propósito — usado por testes para nunca tocar hardware real).
        if camera_module is _CAMERA_NAO_INFORMADA:
            try:
                from vision import camera as camera_module_importado
                camera_module = camera_module_importado
            except Exception:
                camera_module = None
        self.camera_module = camera_module

        if pesquisa_app is _PESQUISA_APP_NAO_INFORMADO:
            try:
                from core import pesquisa_app as pesquisa_app_importado
                pesquisa_app = pesquisa_app_importado
            except Exception:
                pesquisa_app = None
        self.pesquisa_app = pesquisa_app

        self.estado = EstadoAtendimento.INATIVO
        self.roteiro = []
        self.indice_passo = 0
        self.respostas = {}
        self._resposta_pendente = None
        self._pergunta_pendente = None
        self._pergunta_dinamica_passo = None

        self.atendimento_id = None
        self.nome_pessoa = None
        self.titulo_pessoa = None
        self.pessoa_conhecida = False
        self.frase_autorizacao_ouvida = False

        self._nome_pendente = None
        self.sessao_camera = None
        self._tentativas_foto = 0
        self._contador_ack = 0

    def esta_ativo(self):
        return self.estado not in (EstadoAtendimento.INATIVO, EstadoAtendimento.CONCLUIDO)

    # -----------------------------------------------------------
    # CICLO DE VIDA
    # -----------------------------------------------------------
    def _saudacao_por_horario(self):
        hora = datetime.now().hour
        if hora < 12:
            periodo = "Bom dia"
        elif hora < 18:
            periodo = "Boa tarde"
        else:
            periodo = "Boa noite"
        return f"{periodo}! Seja bem-vindo. Com quem estou falando?"

    def iniciar(self, roteiro, saudacao=None):
        """Inicia um atendimento do zero. Retorna a saudação/pergunta inicial."""
        self.roteiro = list(roteiro or [])
        self.indice_passo = 0
        self.respostas = {}
        self._resposta_pendente = None
        self._pergunta_dinamica_passo = None

        self.atendimento_id = memory.novo_id_atendimento()
        self.nome_pessoa = None
        self.titulo_pessoa = None
        self.pessoa_conhecida = False
        self.frase_autorizacao_ouvida = False
        self._nome_pendente = None
        self.sessao_camera = None
        self._tentativas_foto = 0
        self._contador_ack = 0

        self.estado = EstadoAtendimento.AGUARDANDO_NOME
        self._pergunta_pendente = saudacao or self._saudacao_por_horario()
        return self._pergunta_pendente

    def finalizar(self):
        dados = dict(self.respostas)
        self.limpar_estado()
        return dados

    def limpar_estado(self):
        """
        Reseta TUDO — nunca deixa nome, respostas ou foto de uma
        pessoa vazarem para o atendimento seguinte.
        """
        # Se a sessão for encerrada com uma foto tirada mas ainda sem
        # decisão final (nem confirmada, nem recusada), descarta a
        # prévia agora — nunca deixa a imagem de uma pessoa disponível
        # para a próxima sessão.
        if self.sessao_camera is not None:
            try:
                self.sessao_camera.descartar_se_pendente()
            except Exception:
                pass

        self.estado = EstadoAtendimento.INATIVO
        self.roteiro = []
        self.indice_passo = 0
        self.respostas = {}
        self._resposta_pendente = None
        self._pergunta_pendente = None
        self._pergunta_dinamica_passo = None
        self.atendimento_id = None
        self.nome_pessoa = None
        self.titulo_pessoa = None
        self.pessoa_conhecida = False
        self.frase_autorizacao_ouvida = False
        self._nome_pendente = None
        self.sessao_camera = None
        self._tentativas_foto = 0
        self._contador_ack = 0

    def iniciar_proximo(self, roteiro):
        """Limpa o atendimento atual (se houver) e prepara o próximo, em sequência."""
        self.limpar_estado()
        return self.iniciar(roteiro, saudacao=SAUDACAO_PROXIMO_ATENDIMENTO)

    def mensagem_nao_entendi(self):
        """Usado pelo chamador (core/alfa_core.py) quando o reconhecimento de voz não capturou nada."""
        if self.estado == EstadoAtendimento.AGUARDANDO_NOME:
            return MENSAGEM_NAO_ENTENDI_NOME
        return MENSAGEM_NAO_ENTENDI_GENERICA

    # -----------------------------------------------------------
    # IDENTIFICAÇÃO DA PESSOA
    # -----------------------------------------------------------
    def _extrair_nome(self, texto_ouvido):
        texto = _PREFIXOS_NOME.sub("", texto_ouvido.strip())
        texto = texto.strip().rstrip(".!?")
        return texto or texto_ouvido.strip()

    def _primeiro_nome(self):
        if not self.nome_pessoa:
            return ""
        return self.nome_pessoa.strip().split()[0]

    # Exceções conhecidas: nomes masculinos comuns no Brasil que
    # terminam em "a" (a heurística abaixo por padrão os trataria como
    # femininos). Lista deliberadamente pequena e ajustável.
    _NOMES_MASCULINOS_TERMINADOS_EM_A = {"luca"}

    def _formatar_titulo(self, nome):
        """
        "Seu"/"Dona" são as formas de tratamento respeitoso e informal
        já consagradas no português do Brasil para se dirigir a
        alguém pelo primeiro nome — não é uma invenção de conteúdo,
        é convenção de tratamento. Como não há como saber o gênero
        com certeza a partir só do nome, usa uma heurística comum
        (nomes terminados em "a" tendem a ser femininos em
        português) com uma pequena lista de exceções conhecidas;
        continua sendo apenas uma estimativa, não uma verificação.
        """
        primeiro = nome.strip().split()[0] if nome.strip() else nome
        primeiro_lower = primeiro.lower()

        parece_feminino = (
            primeiro_lower.endswith("a")
            and primeiro_lower not in self._NOMES_MASCULINOS_TERMINADOS_EM_A
        )

        tratamento = "Dona" if parece_feminino else "Seu"
        return f"{tratamento} {primeiro}"

    def _processar_nome_ouvido(self, texto_ouvido):
        if not texto_ouvido:
            return {"acao": "repetir_pergunta", "mensagem": MENSAGEM_NAO_ENTENDI_NOME}

        self._nome_pendente = self._extrair_nome(texto_ouvido)
        self.estado = EstadoAtendimento.CONFIRMANDO_NOME
        self._pergunta_pendente = f"Só para confirmar, estou falando com {self._nome_pendente}?"
        return {"acao": "confirmar", "mensagem": self._pergunta_pendente}

    def _processar_confirmacao_nome(self, texto_ouvido):
        confirmou = interpretar_resposta(texto_ouvido)

        if confirmou is None:
            return {"acao": "repetir_confirmacao", "mensagem": self._pergunta_pendente}

        if not confirmou:
            self._nome_pendente = None
            self.estado = EstadoAtendimento.AGUARDANDO_NOME
            self._pergunta_pendente = MENSAGEM_NAO_ENTENDI_NOME
            return {"acao": "repetir_pergunta", "mensagem": self._pergunta_pendente}

        self.nome_pessoa = self._nome_pendente
        self.titulo_pessoa = self._formatar_titulo(self.nome_pessoa)
        self.pessoa_conhecida = identidade.eh_pessoa_conhecida(self.nome_pessoa)
        self._nome_pendente = None

        return self._iniciar_roteiro_apos_identificacao()

    def _preparar_ambiente_pesquisa(self):
        """
        Localiza a janela da pesquisa já aberta e traz para frente;
        se não encontrar nenhuma, tenta abrir o aplicativo real (ver
        core/pesquisa_app.py) — a BETA não deve exigir que a tela já
        esteja aberta antes de começar. Best-effort: nunca bloqueia o
        atendimento, e nunca inventa que encontrou algo que não achou.
        """
        if self.pesquisa_app is None:
            return None
        try:
            return self.pesquisa_app.localizar_ou_abrir()
        except Exception:
            return None

    def _iniciar_roteiro_apos_identificacao(self):
        mensagem_boas_vindas = f"Perfeito, {self.titulo_pessoa}. Vamos começar."

        resultado_ambiente = self._preparar_ambiente_pesquisa()
        if resultado_ambiente == "nao_encontrada":
            mensagem_boas_vindas += (
                " Não encontrei a tela da pesquisa aberta — pode abri-la para mim continuar?"
            )

        # "Identificar a tela" (item 7 do fluxo): best-effort, nunca
        # bloqueia o atendimento — ver identificar_tela().
        self.identificar_tela()

        if not self.roteiro:
            self.estado = EstadoAtendimento.CONCLUIDO
            return {"acao": "finalizado", "mensagem": self._mensagem_conclusao(), "dados": self.finalizar()}

        self.indice_passo = 0
        self._executar_passos_de_navegacao()
        self._preparar_proximo_passo()

        proxima = self.pergunta_atual()
        if proxima is None:
            self.estado = EstadoAtendimento.CONCLUIDO
            return {"acao": "finalizado", "mensagem": self._mensagem_conclusao(), "dados": self.finalizar()}

        return {"acao": "proxima_pergunta", "mensagem": mensagem_boas_vindas, "proxima_pergunta": proxima}

    def _mensagem_conclusao(self):
        if self.titulo_pessoa:
            return f"Pronto, {self.titulo_pessoa}. Seu atendimento foi concluído. Muito obrigado."
        return "Pronto. Seu atendimento foi concluído. Muito obrigado."

    # -----------------------------------------------------------
    # PASSOS DO ROTEIRO (perguntar / confirmar / preencher / avançar)
    # -----------------------------------------------------------
    def _passo_atual(self):
        if self.indice_passo >= len(self.roteiro):
            return None
        return self.roteiro[self.indice_passo]

    def identificar_tela(self):
        """
        Descreve o que está na tela agora (via visão local/IA), para
        confirmar que o atendimento está na tela certa. Best-effort e
        com timeout curto: se a visão não estiver disponível ou
        demorar demais, não bloqueia o atendimento (offline-first —
        serviços online são sempre opcionais).
        """
        if self.vision_module is None:
            return None
        try:
            return self.vision_module.analisar_tela(timeout=4)
        except Exception:
            return None

    def pergunta_atual(self):
        if self.estado in (
            EstadoAtendimento.AGUARDANDO_NOME,
            EstadoAtendimento.CONFIRMANDO_NOME,
            EstadoAtendimento.AGUARDANDO_AUTORIZACAO,
            EstadoAtendimento.AGUARDANDO_CONSENTIMENTO_FOTO,
            EstadoAtendimento.AGUARDANDO_CONFIRMACAO_FOTO,
        ):
            return self._pergunta_pendente

        passo = self._passo_atual()
        if passo is None:
            return None
        return (
            passo.get("pergunta")
            or self._pergunta_dinamica_passo
            or f"Qual o valor de {passo.get('campo')}?"
        )

    def _pergunta_confirmacao_campo(self, passo):
        modelo = passo.get("confirmar_template")
        if modelo:
            try:
                return modelo.format(valor=self._resposta_pendente, campo=passo.get("campo", ""))
            except Exception:
                pass
        return pergunta_de_confirmacao(passo.get("campo", "isso"), self._resposta_pendente)

    def _formatar_lista_opcoes(self, opcoes):
        opcoes = [o for o in opcoes if o]
        if not opcoes:
            return ""
        if len(opcoes) == 1:
            return opcoes[0]
        return ", ".join(opcoes[:-1]) + f" ou {opcoes[-1]}"

    def _pergunta_dinamica_opcao(self, passo):
        """
        Monta a pergunta lendo as opções REAIS do elemento na tela
        (nunca uma lista inventada) — ver
        computer/form_filler.py:listar_opcoes().
        """
        campo = passo.get("campo", "")
        pergunta_base = passo.get("pergunta") or f"Qual é a sua opção para {campo}?"

        if self.form_filler is None:
            return pergunta_base

        try:
            opcoes = self.form_filler.listar_opcoes(campo, automation_id=passo.get("automation_id"))
        except Exception:
            opcoes = []

        lista = self._formatar_lista_opcoes(opcoes)
        if lista:
            return f"{pergunta_base} As opções são: {lista}."
        return pergunta_base

    def _pergunta_opcao_botao(self, passo):
        # Frase mais natural que "Qual é a sua resposta para Resposta
        # principal?" (redundante quando o campo já se chama isso).
        pergunta_base = passo.get("pergunta") or "Qual é a sua resposta?"
        lista = self._formatar_lista_opcoes(passo.get("opcoes") or [])
        if lista:
            return f"{pergunta_base} As opções são: {lista}."
        return pergunta_base

    def _proxima_confirmacao_natural(self):
        ack = CONFIRMACOES_NATURAIS[self._contador_ack % len(CONFIRMACOES_NATURAIS)]
        self._contador_ack += 1
        return ack

    def _preparar_proximo_passo(self):
        passo = self._passo_atual()
        if passo is None:
            return

        if (
            passo.get("requer_autorizacao")
            and not self.pessoa_conhecida
            and not self.frase_autorizacao_ouvida
        ):
            self.estado = EstadoAtendimento.AGUARDANDO_AUTORIZACAO
            self._pergunta_pendente = (
                "Essa informação exige autorização do Rinaldo. Se você tiver "
                "autorização, pode dizer a frase agora."
            )
            return

        if passo.get("tipo") == "foto":
            self.estado = EstadoAtendimento.AGUARDANDO_CONSENTIMENTO_FOTO
            self._tentativas_foto = 0
            self._pergunta_pendente = self._pergunta_consentimento_foto(passo)
            return

        if passo.get("tipo") == "opcao" and not passo.get("pergunta"):
            self._pergunta_dinamica_passo = self._pergunta_dinamica_opcao(passo)
        elif passo.get("tipo") == "opcao_botao" and not passo.get("pergunta"):
            self._pergunta_dinamica_passo = self._pergunta_opcao_botao(passo)
        else:
            self._pergunta_dinamica_passo = None

        self.estado = EstadoAtendimento.PERGUNTANDO

    def _avancar_passo_e_preparar(self):
        self.indice_passo += 1
        self._executar_passos_de_navegacao()
        self._preparar_proximo_passo()

    def _resultado_apos_avancar(self, mensagem):
        proxima = self.pergunta_atual()
        if proxima is None:
            # Ao concluir TODO o roteiro, a mensagem de encerramento
            # (item 14 do fluxo) sempre prevalece sobre o aviso de
            # preenchimento do último campo — nunca os dois juntos.
            # IMPORTANTE: calcular a mensagem ANTES de finalizar() —
            # finalizar() chama limpar_estado(), que zera
            # titulo_pessoa; calcular depois produziria "Pronto." sem
            # o nome da pessoa.
            mensagem_final = self._mensagem_conclusao()
            dados = self.finalizar()
            return {"acao": "finalizado", "mensagem": mensagem_final, "dados": dados}
        return {"acao": "proxima_pergunta", "mensagem": mensagem, "proxima_pergunta": proxima}

    def processar_resposta(self, texto_ouvido):
        """
        Recebe o texto ouvido do usuário e decide o próximo passo.

        Retorna um dict com pelo menos a chave "acao", uma de:
            "confirmar", "repetir_confirmacao", "repetir_pergunta",
            "proxima_pergunta", "finalizado".
        """
        texto_ouvido = (texto_ouvido or "").strip()

        if self.estado == EstadoAtendimento.AGUARDANDO_NOME:
            return self._processar_nome_ouvido(texto_ouvido)

        if self.estado == EstadoAtendimento.CONFIRMANDO_NOME:
            return self._processar_confirmacao_nome(texto_ouvido)

        if self.estado == EstadoAtendimento.AGUARDANDO_AUTORIZACAO:
            return self._processar_autorizacao(texto_ouvido)

        if self.estado == EstadoAtendimento.AGUARDANDO_CONSENTIMENTO_FOTO:
            return self._processar_consentimento_foto(texto_ouvido)

        if self.estado == EstadoAtendimento.AGUARDANDO_CONFIRMACAO_FOTO:
            return self._processar_confirmacao_foto(texto_ouvido)

        passo = self._passo_atual()
        if passo is None:
            return {"acao": "finalizado", "mensagem": self._mensagem_conclusao(), "dados": self.finalizar()}

        if self.estado == EstadoAtendimento.AGUARDANDO_CONFIRMACAO:
            return self._processar_confirmacao(texto_ouvido, passo)

        # Pedido de pular ("pular", "não tenho essa informação",
        # "prefiro não responder"...) — só aceito para campos NÃO
        # obrigatórios; nunca preenche nada na tela real nesse caso.
        if eh_pedido_de_pular(texto_ouvido):
            if not passo.get("obrigatorio", False):
                return self._pular_campo(passo)
            return {
                "acao": "repetir_pergunta",
                "mensagem": (
                    "Essa informação é obrigatória para a pesquisa, não dá para pular. "
                    + self.pergunta_atual()
                ),
            }

        # Estado PERGUNTANDO: acabou de ouvir a resposta bruta ao passo atual.
        self._resposta_pendente = texto_ouvido

        if passo.get("confirmar", True):
            self.estado = EstadoAtendimento.AGUARDANDO_CONFIRMACAO
            self._pergunta_pendente = self._pergunta_confirmacao_campo(passo)
            return {"acao": "confirmar", "mensagem": self._pergunta_pendente}

        return self._registrar_e_avancar(passo)

    def _pular_campo(self, passo):
        """Registra o campo como não informado e avança, sem tocar na tela real."""
        campo = passo.get("campo", f"passo_{self.indice_passo}")
        self.respostas[campo] = None
        self._resposta_pendente = None
        self._avancar_passo_e_preparar()
        return self._resultado_apos_avancar(f"Sem problema, deixei '{campo}' em branco.")

    def _processar_confirmacao(self, texto_ouvido, passo):
        # A pessoa pode mudar de ideia na hora da confirmação e pedir
        # para pular, em vez de responder sim/não à confirmação.
        if eh_pedido_de_pular(texto_ouvido) and not passo.get("obrigatorio", False):
            return self._pular_campo(passo)

        confirmou = interpretar_resposta(texto_ouvido)

        if confirmou is None:
            return {"acao": "repetir_confirmacao", "mensagem": self._pergunta_confirmacao_campo(passo)}

        if not confirmou:
            self._resposta_pendente = None
            self.estado = EstadoAtendimento.PERGUNTANDO
            return {"acao": "repetir_pergunta", "mensagem": self.pergunta_atual()}

        return self._registrar_e_avancar(passo)

    def _preencher_campo_real(self, passo, campo, valor):
        """
        Executa o preenchimento REAL na tela, com verificação e uma
        nova tentativa segura em caso de falha ao confirmar o valor
        (ver computer/form_filler.py:FalhaDeVerificacao). Nunca avança
        fingindo sucesso: se as tentativas se esgotarem, devolve
        `verificado=False` para quem chamou avisar a dificuldade.
        """
        if self.form_filler is None:
            return "Perfeito.", True

        automation_id = passo.get("automation_id")
        tipo = passo.get("tipo")
        ultimo_erro = None

        for _ in range(MAX_TENTATIVAS_PREENCHIMENTO):
            try:
                if tipo == "checkbox":
                    return self.form_filler.marcar_checkbox(campo, automation_id=automation_id), True
                if tipo == "opcao_botao":
                    return self.form_filler.clicar_botao(valor), True
                if tipo == "opcao":
                    return self.form_filler.selecionar_opcao(campo, valor, automation_id=automation_id), True
                return self.form_filler.preencher_texto(campo, valor, automation_id=automation_id), True
            except FalhaDeVerificacao as erro:
                # Só a falha de verificação justifica tentar de novo —
                # pode ter sido uma disputa momentânea de foco de tela.
                ultimo_erro = erro
                continue
            except Exception as erro:
                # Qualquer outro erro (elemento não encontrado, bug
                # inesperado no form_filler, etc.): não tenta de novo
                # às cegas. O detalhe técnico vai só para o log — a
                # pessoa entrevistada não precisa ouvir uma mensagem
                # de exceção do Python.
                print(f"[BETA] Não encontrei/não consegui preencher '{campo}': {erro}")
                return (
                    f"Tive uma dificuldade para localizar '{campo}' na tela. "
                    "Vou continuar, mas convém revisar esse campo depois.",
                    False,
                )

        print(f"[BETA] Falha de verificação em '{campo}' mesmo após nova tentativa: {ultimo_erro}")
        return (
            f"Tive uma dificuldade para confirmar '{campo}' na tela, mesmo tentando de "
            "novo. Vou continuar, mas convém revisar esse campo depois.",
            False,
        )

    def _registrar_e_avancar(self, passo):
        campo = passo.get("campo", f"passo_{self.indice_passo}")
        self.respostas[campo] = self._resposta_pendente

        mensagem_tecnica, verificado = self._preencher_campo_real(
            passo, campo, self._resposta_pendente
        )

        if verificado:
            # Sucesso: fala natural ("Perfeito.", "Entendido.") em vez
            # da mensagem técnica de preenchimento — a pessoa não
            # precisa ouvir "Preenchi 'X' com 'Y'" a cada resposta, só
            # quando algo dá errado (aí a clareza importa mais que a
            # naturalidade).
            mensagem_preenchimento = self._proxima_confirmacao_natural()
        else:
            self.respostas[f"{campo} (aviso)"] = "preenchimento não verificado na tela"
            mensagem_preenchimento = mensagem_tecnica

        self._resposta_pendente = None
        self._avancar_passo_e_preparar()
        return self._resultado_apos_avancar(mensagem_preenchimento)

    # -----------------------------------------------------------
    # AUTORIZAÇÃO (ver core/identidade.py e seção SEGURANÇA)
    # -----------------------------------------------------------
    def _processar_autorizacao(self, texto_ouvido):
        if identidade.contem_frase_autorizacao(texto_ouvido):
            self.frase_autorizacao_ouvida = True
            self._preparar_proximo_passo()
            return self._resultado_apos_avancar("Autorização confirmada. Vamos continuar.")

        self._avancar_passo_e_preparar()
        return self._resultado_apos_avancar("Sem autorização, vou pular essa pergunta.")

    # -----------------------------------------------------------
    # FOTO (consentimento -> capturar -> prévia -> confirmar/refazer)
    # -----------------------------------------------------------
    def _pergunta_consentimento_foto(self, passo):
        pergunta_customizada = passo.get("pergunta_consentimento")
        if pergunta_customizada:
            return pergunta_customizada

        # "Seu João, preciso tirar uma foto..." — usa o TRATAMENTO
        # confirmado (Seu/Dona + nome), não só o primeiro nome solto.
        tratamento = self.titulo_pessoa or self._primeiro_nome()
        prefixo = f"{tratamento}, " if tratamento else ""
        return f"{prefixo}preciso tirar uma foto para registrar seu atendimento. Posso tirar?"

    def _processar_consentimento_foto(self, texto_ouvido):
        concedido = interpretar_resposta(texto_ouvido)

        if concedido is None:
            return {"acao": "repetir_confirmacao", "mensagem": self._pergunta_pendente}

        if not concedido:
            passo = self._passo_atual()

            # Fotografia obrigatória: não dá para simplesmente seguir
            # sem ela — insiste educadamente (mesma filosofia dos
            # campos de texto obrigatórios).
            if passo and passo.get("obrigatorio", False):
                self._pergunta_pendente = (
                    "Essa pesquisa exige uma fotografia para continuar o atendimento. "
                    "Posso tirar a foto agora?"
                )
                return {"acao": "repetir_confirmacao", "mensagem": self._pergunta_pendente}

            # Registra a recusa no próprio registro do atendimento
            # (quando o roteiro tiver um campo para isso), em vez de
            # simplesmente não deixar rastro nenhum da pergunta.
            if passo:
                campo_foto = passo.get("campo", "Fotografia")
                self.respostas[campo_foto] = "Não autorizada pelo entrevistado"

            self.sessao_camera = None
            self._avancar_passo_e_preparar()
            return self._resultado_apos_avancar("Sem problema, vamos seguir sem a foto.")

        return self._capturar_e_mostrar_foto()

    def _refocar_pesquisa(self):
        """
        Traz a janela da pesquisa de volta para frente. Necessário
        depois de mostrar a prévia da foto — abrir o visualizador de
        imagens do Windows rouba o foco, e sem isso o próximo
        preenchimento (UI Automation/clique) iria mirar na janela
        errada, exigindo alguém clicar de volta manualmente.
        Reaproveita _preparar_ambiente_pesquisa(): mesma chamada
        best-effort, só que aqui o resultado não interessa.
        """
        self._preparar_ambiente_pesquisa()

    def _capturar_e_mostrar_foto(self):
        eh_nova_tentativa = self._tentativas_foto > 0

        if self.camera_module is None:
            self._avancar_passo_e_preparar()
            return self._resultado_apos_avancar(
                "Não consegui acessar a câmera agora. Vamos seguir sem a foto."
            )

        self._tentativas_foto += 1
        self.sessao_camera = self.camera_module.SessaoCamera()
        self.sessao_camera.registrar_consentimento(True)

        try:
            self.sessao_camera.capturar_foto()
            self.sessao_camera.mostrar_previa()
        except Exception as erro:
            print(f"[BETA] Falha ao capturar foto: {erro}")
            self.sessao_camera = None
            self._avancar_passo_e_preparar()
            return self._resultado_apos_avancar(
                "Não consegui tirar a foto agora. Vamos seguir sem ela."
            )

        self.estado = EstadoAtendimento.AGUARDANDO_CONFIRMACAO_FOTO
        pergunta = "Ficou uma boa foto? Posso usar essa, ou prefere que eu tire de novo?"
        if eh_nova_tentativa:
            pergunta = f"Sem problema, vamos tentar de novo. {pergunta}"
        self._pergunta_pendente = pergunta
        return {"acao": "confirmar", "mensagem": self._pergunta_pendente}

    def _processar_confirmacao_foto(self, texto_ouvido):
        aceitou = interpretar_resposta(texto_ouvido)

        if aceitou is None:
            return {"acao": "repetir_confirmacao", "mensagem": self._pergunta_pendente}

        passo = self._passo_atual()
        campo_foto = passo.get("campo", "Fotografia") if passo else "Fotografia"

        if aceitou:
            mensagem_foto = "Foto registrada. Vamos continuar."
            try:
                self.sessao_camera.confirmar(True)
                # A foto fica vinculada ao ID ÚNICO deste atendimento
                # (gerado em iniciar()/iniciar_proximo() — nunca o
                # mesmo entre pessoas diferentes), garantindo que
                # nunca seja associada à pessoa errada.
                caminho_final = self.sessao_camera.associar_ao_atendimento(self.atendimento_id)
                self.respostas[campo_foto] = caminho_final
            except Exception as erro:
                print(f"[BETA] Falha ao salvar a foto: {erro}")
                mensagem_foto = "Não consegui salvar a foto, mas vamos continuar."
                self.respostas[campo_foto] = "Falha ao salvar a fotografia"
        elif self._tentativas_foto < MAX_TENTATIVAS_FOTO:
            self.sessao_camera.confirmar(False)
            return self._capturar_e_mostrar_foto()
        else:
            self.sessao_camera.confirmar(False)
            self.respostas[campo_foto] = "Não foi possível obter uma foto satisfatória"
            mensagem_foto = "Sem problema, vamos seguir sem a foto."

        # Devolve o foco para a pesquisa antes de continuar — ver
        # _refocar_pesquisa().
        self._refocar_pesquisa()
        self._avancar_passo_e_preparar()
        return self._resultado_apos_avancar(mensagem_foto)

    # -----------------------------------------------------------
    # NAVEGAÇÃO ("Próximo"/"Avançar"/"Voltar"/"Confirmar" na tela)
    # -----------------------------------------------------------
    def _executar_passos_de_navegacao(self):
        """
        Executa automaticamente passos do tipo "navegacao" (sem
        perguntar nada à pessoa), avançando até o próximo passo real
        ou até o fim do roteiro.
        """
        while True:
            passo = self._passo_atual()
            if passo is None or passo.get("tipo") != "navegacao":
                break
            self._executar_navegacao(passo)
            self.indice_passo += 1

    def _executar_navegacao(self, passo):
        if self.form_filler is None:
            return None

        nome_botao = passo.get("nome")
        try:
            if nome_botao:
                # Clica um botão pelo nome REAL na tela (ex.: o botão
                # de envio de uma tela específica, que não se chama
                # "Avançar"/"Confirmar").
                return self.form_filler.clicar_botao(nome_botao, automation_id=passo.get("automation_id"))

            acao = passo.get("acao", "avancar")
            metodo = getattr(self.form_filler, acao, None)
            if metodo is None:
                return None
            return metodo()
        except Exception:
            return None
