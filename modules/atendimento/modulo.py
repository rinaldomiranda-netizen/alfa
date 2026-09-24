"""Adapter do RMD Atendimento dentro da plataforma ALPHA.

Responsabilidade deste arquivo: oferecer um contrato pequeno e estável
para o ALPHA sem duplicar a máquina de estados existente em
``core.atendimento``.
"""

from core.atendimento import AtendimentoBeta, EstadoAtendimento


class AtendimentoModule:
    """Fachada do módulo de atendimento.

    O Alpha Core não precisa conhecer os detalhes do protocolo de
    atendimento. A fachada cria e controla a sessão e expõe apenas
    operações do módulo.
    """

    module_id = "rmd-atendimento"
    version = "5.1.1"

    def __init__(self, **kwargs):
        self.engine = AtendimentoBeta(**kwargs)

    @property
    def estado(self):
        return self.engine.estado

    @property
    def ativo(self):
        return self.engine.esta_ativo()

    def iniciar(self, roteiro, saudacao=None):
        return self.engine.iniciar(roteiro, saudacao=saudacao)

    def responder(self, texto):
        """Encaminha uma resposta para o protocolo já existente.

        O método é deliberadamente fino: regras de confirmação,
        autorização, foto e limpeza de sessão continuam no núcleo de
        atendimento, evitando duas implementações concorrentes.
        """
        return self.engine.processar_resposta(texto)

    def finalizar(self):
        return self.engine.finalizar()

    def iniciar_proximo(self, roteiro):
        return self.engine.iniciar_proximo(roteiro)

    def limpar(self):
        self.engine.limpar_estado()

    def status(self):
        return {
            "id": self.module_id,
            "versao": self.version,
            "ativo": self.ativo,
            "estado": self.estado.value if isinstance(self.estado, EstadoAtendimento) else str(self.estado),
            "atendimento_id": self.engine.atendimento_id,
            "nome_pessoa": self.engine.nome_pessoa,
        }
