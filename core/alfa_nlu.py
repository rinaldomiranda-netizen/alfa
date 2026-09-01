
from sentence_transformers import SentenceTransformer, util
import numpy as np
import re
import unicodedata


class AlfaNLU:

    def __init__(self):

        self.encoder = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2"
        )

        self.intents = {

            "MOVER_MOUSE": [
                "mova o mouse para esquerda",
                "mexa o mouse para esquerda",
                "macho mouse para esquerda",
                "mecho mouse para esquerda",
                "leve o mouse para esquerda",
                "mova o mause para esquerda",
                "mova o mouse para direita",
                "mexa o mouse para direita",
                "leve o mouse para cima",
                "suba o mouse",
                "mova o mouse para baixo",
                "des?a o mouse",
                "baixe o mouse",
                "coloque o mouse no centro"
            ],

            "POSICAO_MOUSE": [
                "qual ? a posi??o do mouse",
                "onde est? o mouse",
                "onde fica o cursor"
            ],

            "CLIQUE": [
                "clique",
                "fa?a um clique",
                "clique direito",
                "clique duplo",
                "duplo clique"
            ],

            "ABRIR": [
                "abra a calculadora",
                "abra o programa",
                "inicie a calculadora",
                "execute a calculadora",
                "abra o navegador"
            ],

            "FECHAR": [
                "feche a calculadora",
                "feche o programa",
                "encerre a calculadora",
                "feche o navegador"
            ],

            "COPIAR": [
                "copiar",
                "copie isso",
                "copie o texto"
            ],

            "COLAR": [
                "colar",
                "cole isso",
                "cole o texto"
            ],

            "DESFAZER": [
                "desfazer",
                "desfa?a",
                "volte atr?s"
            ],

            "SELECIONAR_TUDO": [
                "selecione tudo",
                "selecionar tudo"
            ],

            "ENTER": [
                "pressione enter",
                "aperte enter"
            ],

            "ESC": [
                "pressione escape",
                "aperte esc"
            ],

            "VISUALIZAR": [
                "olhe minha tela",
                "veja minha tela",
                "analise minha tela"
            ],

            "CAMERA": [
                "veja pela c?mera",
                "olhe pela c?mera",
                "veja o ambiente"
            ],

            "SAIR": [
                "saia",
                "encerre o alfa",
                "feche o alfa",
                "pare o alfa",
                "alfa saia",
                "alfa pode sair"
            ]
        }

        self.frases = []
        self.mapa = []

        for intent, frases in self.intents.items():

            for frase in frases:

                self.frases.append(
                    self.normalizar(frase)
                )

                self.mapa.append(intent)

        self.vetores = self.encoder.encode(
            self.frases,
            normalize_embeddings=True,
            show_progress_bar=False
        )


    def normalizar(self, texto):

        texto = texto.lower()

        texto = ''.join(
            c for c in unicodedata.normalize(
                "NFD",
                texto
            )
            if unicodedata.category(c) != "Mn"
        )

        texto = re.sub(
            r"\s+",
            " ",
            texto
        )

        return texto.strip()


    def direcao(self, texto):

        texto = self.normalizar(texto)

        if "esquerda" in texto:
            return "esquerda"

        if "direita" in texto:
            return "direita"

        if "cima" in texto or "suba" in texto:
            return "cima"

        if "baixo" in texto or "desca" in texto or "baixe" in texto:
            return "baixo"

        if "centro" in texto or "meio" in texto:
            return "centro"

        return None


    def programa(self, texto):

        texto = self.normalizar(texto)

        for programa in [
            "calculadora",
            "navegador",
            "chrome",
            "edge",
            "notepad",
            "paint"
        ]:

            if programa in texto:
                return programa

        return None


    def interpretar(self, comando):

        texto = self.normalizar(comando)

        # =====================================================
        # PROTE??O SEM?NTICA DO MOUSE
        # =====================================================
        # Se a fala claramente cont?m mouse/cursor + a??o de
        # movimento, nunca permitir que outra inten??o como
        # SAIR ganhe por similaridade.

        tem_mouse = any(x in texto for x in [
            "mouse",
            "mause",
            "maus",
            "cursor",
            "mou",
            "malwe"
        ])

        tem_movimento = any(x in texto for x in [
            "mover",
            "mova",
            "move",
            "mexer",
            "mexa",
            "mexe",
            "meche",
            "mecho",
            "mexo",
            "levar",
            "leve",
            "deslocar",
            "arrastar",
            "subir",
            "suba",
            "descer",
            "desca",
            "baixar",
            "baixe",
            "elevar"
        ])

        if tem_mouse and tem_movimento:

            return {
                "intent": "MOVER_MOUSE",
                "confidence": 1.0,
                "direcao": self.direcao(comando)
            }

        vetor = self.encoder.encode(
            texto,
            normalize_embeddings=True
        )

        scores = util.cos_sim(
            vetor,
            self.vetores
        )[0].cpu().numpy()

        indice = int(np.argmax(scores))

        confianca = float(scores[indice])

        intent = self.mapa[indice]

        if confianca < 0.55:

            return {
                "intent": "DESCONHECIDO",
                "confidence": round(confianca, 3)
            }

        resultado = {
            "intent": intent,
            "confidence": round(confianca, 3)
        }

        if intent == "MOVER_MOUSE":

            resultado["direcao"] = self.direcao(
                comando
            )

        if intent in ["ABRIR", "FECHAR"]:

            resultado["programa"] = self.programa(
                comando
            )

        if intent == "CLIQUE":

            if "direito" in texto:
                resultado["botao"] = "direito"

            elif "duplo" in texto:
                resultado["botao"] = "duplo"

            else:
                resultado["botao"] = "esquerdo"

        return resultado


if __name__ == "__main__":

    nlu = AlfaNLU()

    testes = [
        "alfa mova o mouse para esquerda",
        "alfa macho mouse para esquerda",
        "alfa mecho mouse para direita",
        "alfa suba o mouse",
        "alfa des?a o mouse",
        "alfa onde est? o mouse",
        "alfa clique direito",
        "alfa abra a calculadora",
        "alfa feche a calculadora"
    ]

    for frase in testes:

        print()
        print("FALA:", frase)
        print("=>", nlu.interpretar(frase))
