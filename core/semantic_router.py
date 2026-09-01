
import json
import re
import unicodedata
import urllib.request


class SemanticRouter:

    def __init__(self):
        self.url = "http://127.0.0.1:11434/api/chat"
        self.model = "qwen2.5:0.5b"

    def normalizar(self, texto):
        texto = texto.lower()
        texto = ''.join(
            c for c in unicodedata.normalize("NFD", texto)
            if unicodedata.category(c) != "Mn"
        )
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto

    def interpretar(self, comando):

        texto = self.normalizar(comando)

        # =====================================================
        # COMANDOS ?BVIOS ? ZERO IA
        # =====================================================

        if any(x in texto for x in [
            "sair",
            "saia",
            "encerre alfa",
            "feche o alfa",
            "desligue o alfa"
        ]):
            return {
                "intent": "SAIR"
            }

        # =====================================================
        # MOUSE
        # =====================================================

        palavras_mouse = [
            "mouse", "mause", "maus", "malwe",
            "malve", "mou", "mousee"
        ]

        palavras_mover = [
            "mover", "mova", "move", "mexer", "mexa", "mecho", "meche", "mexe",
            "levar", "leve", "colocar", "coloque",
            "arrastar", "arraste", "deslocar",
            "andar", "jogar", "joga", "manda",
            "mandar", "puxar", "puxe", "empurrar",
            "mex", "moval", "novo", "novou", "noval", "mecho", "meche", "mexo"
        ]

        tem_mouse = any(x in texto for x in palavras_mouse)
        tem_mover = any(x in texto for x in palavras_mover)

        if tem_mouse and tem_mover:


            direcao = None

            if any(x in texto for x in [
                "esquerda", "esquerdo", "lado esquerdo"
            ]):
                direcao = "esquerda"

            elif any(x in texto for x in [
                "direita", "direito", "lado direito"
            ]):
                direcao = "direita"

            elif any(x in texto for x in [
                "cima", "para cima", "pra cima",
                "acima", "alto"
            ]):
                direcao = "cima"

            elif any(x in texto for x in [
                "baixo", "para baixo", "pra baixo",
                "abaixo"
            ]):
                direcao = "baixo"

            elif any(x in texto for x in [
                "centro", "meio"
            ]):
                direcao = "centro"

            return {
                "intent": "MOVER_MOUSE",
                "direcao": direcao
            }

        # =====================================================
        # POSI??O DO MOUSE
        # =====================================================

        if (
            "posicao do mouse" in texto
            or "onde esta o mouse" in texto
            or "onde fica o mouse" in texto
        ):
            return {
                "intent": "POSICAO_MOUSE"
            }

        # =====================================================
        # CLIQUE
        # =====================================================

        if any(x in texto for x in [
            "clique", "clicar", "clica", "clic"
        ]):

            if "direito" in texto:
                botao = "direito"

            elif "duplo" in texto or "dupla" in texto:
                botao = "duplo"

            else:
                botao = "esquerdo"

            return {
                "intent": "CLIQUE",
                "botao": botao
            }

        # =====================================================
        # TECLADO
        # =====================================================

        if "copiar" in texto or "copie" in texto:
            return {"intent": "COPIAR"}

        if "colar" in texto or "cole" in texto:
            return {"intent": "COLAR"}

        if "desfazer" in texto or "desfaca" in texto:
            return {"intent": "DESFAZER"}

        if "selecionar tudo" in texto:
            return {"intent": "SELECIONAR_TUDO"}

        if "pressione enter" in texto or "aperte enter" in texto:
            return {"intent": "ENTER"}

        if "pressione esc" in texto or "aperte esc" in texto:
            return {"intent": "ESC"}

        # =====================================================
        # IA SEM?NTICA ? SOMENTE SE N?O FOI POSS?VEL LOCALMENTE
        # =====================================================

        prompt = """
Voc? ? o interpretador de comandos do ALFA.

O usu?rio fala portugu?s brasileiro.

Transforme a frase em UMA inten??o.

N?o converse.
N?o explique.
N?o diga que ? uma IA.
N?o diga que n?o pode controlar o computador.

Responda SOMENTE JSON v?lido.

Inten??es poss?veis:

MOVER_MOUSE
CLIQUE
POSICAO_MOUSE
COPIAR
COLAR
DESFAZER
SELECIONAR_TUDO
ENTER
ESC
ABRIR
FECHAR
VISUALIZAR
CAMERA
SAIR
DESCONHECIDO

Exemplos:

"mexa o mouse para esquerda"
{"intent":"MOVER_MOUSE","direcao":"esquerda"}

"joga o mouse para direita"
{"intent":"MOVER_MOUSE","direcao":"direita"}

"leva o mouse pra cima"
{"intent":"MOVER_MOUSE","direcao":"cima"}

"onde est? o mouse"
{"intent":"POSICAO_MOUSE"}

"clique direito"
{"intent":"CLIQUE","botao":"direito"}

"feche a calculadora"
{"intent":"FECHAR","programa":"calculadora"}

"abra a calculadora"
{"intent":"ABRIR","programa":"calculadora"}

"olhe minha tela"
{"intent":"VISUALIZAR"}

"veja pela c?mera"
{"intent":"CAMERA"}

"saia"
{"intent":"SAIR"}

Usu?rio:
""" + comando

        dados = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 60
            },
            "keep_alive": "10m"
        }

        try:

            requisicao = urllib.request.Request(
                self.url,
                data=json.dumps(dados).encode("utf-8"),
                headers={
                    "Content-Type": "application/json"
                }
            )

            with urllib.request.urlopen(
                requisicao,
                timeout=8
            ) as resposta:

                resultado = json.loads(
                    resposta.read().decode("utf-8")
                )

            conteudo = resultado["message"]["content"].strip()

            inicio = conteudo.find("{")
            fim = conteudo.rfind("}")

            if inicio >= 0 and fim > inicio:

                json_texto = conteudo[inicio:fim + 1]

                try:
                    return json.loads(json_texto)
                except:
                    pass

        except Exception:
            pass

        return {
            "intent": "DESCONHECIDO"
        }
