"""
Registro de ferramentas do agente (Tool Registry).

Cada ferramenta é um contrato simples: nome, descrição, parâmetros
esperados, categoria de permissão (ver security/permissions.py) e uma
função executora real, com uma verificação OPCIONAL que confirma o
resultado de verdade em vez de assumir sucesso só porque a chamada não
lançou exceção.

O núcleo do agente (core/router.py, core/alfa_core.py) nunca precisa
conhecer os detalhes de cada ferramenta — só chama
RegistroFerramentas.executar(nome, **parametros). Adicionar uma
ferramenta nova nunca exige tocar no roteador nem criar mais um ramo
`if kind == ...` em algum lugar central.
"""

from security.permissions import CATEGORIAS_QUE_EXIGEM_CONFIRMACAO


class ResultadoFerramenta:
    """Resultado de executar UMA ferramenta.

    `verificado` é sempre True, False ou None — nunca inventado:
    None significa "esta ferramenta não sabe verificar o próprio
    resultado", não "verifiquei e deu certo".
    """

    def __init__(self, sucesso, mensagem, dados=None, verificado=None, requer_confirmacao=False):
        self.sucesso = sucesso
        self.mensagem = mensagem
        self.dados = dados
        self.verificado = verificado
        self.requer_confirmacao = requer_confirmacao

    def __repr__(self):
        return (
            f"ResultadoFerramenta(sucesso={self.sucesso}, verificado={self.verificado}, "
            f"mensagem={self.mensagem!r})"
        )


class Ferramenta:
    def __init__(self, nome, descricao, parametros, categoria, funcao, verificador=None):
        self.nome = nome
        self.descricao = descricao
        # dict {nome_parametro: descrição} — documentação legível, sem
        # validação rígida de schema nesta fase (YAGNI: nenhuma
        # ferramenta atual precisa disso para funcionar corretamente).
        self.parametros = parametros
        self.categoria = categoria  # BASIC | FILES | SYSTEM | SENSITIVE
        # callable(**kwargs) -> "mensagem" OU (sucesso: bool, mensagem)
        self.funcao = funcao
        # callable(**kwargs) -> True | False | None, opcional
        self.verificador = verificador


class RegistroFerramentas:
    """O Tool Registry propriamente dito."""

    def __init__(self):
        self._ferramentas = {}

    def registrar(self, ferramenta):
        self._ferramentas[ferramenta.nome] = ferramenta

    def obter(self, nome):
        return self._ferramentas.get(nome)

    def listar(self):
        return list(self._ferramentas.values())

    def executar(self, nome, confirmado=False, **kwargs):
        ferramenta = self.obter(nome)
        if ferramenta is None:
            return ResultadoFerramenta(False, f"Ferramenta '{nome}' não está registrada.")

        if ferramenta.categoria in CATEGORIAS_QUE_EXIGEM_CONFIRMACAO and not confirmado:
            return ResultadoFerramenta(
                False,
                f"A ação '{ferramenta.descricao}' exige confirmação antes de executar.",
                requer_confirmacao=True,
            )

        try:
            saida = ferramenta.funcao(**kwargs)
        except Exception as erro:
            return ResultadoFerramenta(False, f"Falha ao executar '{nome}': {erro}")

        # Componentes já existentes no projeto ora devolvem só uma
        # string (ex.: computer/executor.py), ora (sucesso, mensagem),
        # ora (sucesso, mensagem, dados) quando uma etapa seguinte do
        # Planner precisa de um valor estruturado (ex.: endereço de
        # célula achado) — aceita os três formatos sem forçar ninguém
        # a mudar assinatura só para caber no registro.
        dados = None
        if isinstance(saida, tuple):
            if len(saida) == 3:
                sucesso, mensagem, dados = saida
            else:
                sucesso, mensagem = saida
        else:
            sucesso, mensagem = True, saida

        verificado = None
        if sucesso and ferramenta.verificador is not None:
            try:
                verificado = ferramenta.verificador(**kwargs)
            except Exception:
                verificado = None

        return ResultadoFerramenta(sucesso, mensagem, dados=dados, verificado=verificado)
