"""
Skill Registry — descoberta de habilidades instaláveis (ver
skills/<nome>/manifest.json), FASE A da expansão de plataforma
(skills / marketplace / perfis empresariais / integrações / totem /
devices / cloud admin / updater / mobile).

Uma "skill" aqui é só METADADO (nome, descrição, versão, autor,
permissões, ferramentas que expõe, intenções, configuração,
dependências, compatibilidade, capacidade offline) — este registro
NUNCA importa nem executa código de uma skill sozinho; toda execução
real continua passando pelo Tool Registry já existente
(agente/ferramentas.py -> RegistroFerramentas) + Permission Manager
(security/permissions.py) + Verifier, exatamente como word/excel/
powerpoint já funcionam hoje via agente/registro_padrao.py. Isso
evita abrir uma superfície nova de "executar código arbitrário de uma
skill" sem passar pelas mesmas checagens de sempre (item 11 do pedido
de expansão: "não permitir que uma habilidade execute código
arbitrário sem passar pelo sistema de permissões").

Ativar/desativar uma skill (ver ativar/desativar) só controla se ela
aparece como disponível — nunca impede nem libera execução por si só;
quem decide o que pode rodar continua sendo o Tool Registry.
"""

import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_SKILLS_PADRAO = os.path.join(BASE, "skills")
CAMINHO_ESTADO_PADRAO = os.path.join(BASE, "config", "skills_estado.json")

CAMPOS_OBRIGATORIOS = ("nome", "descricao", "versao")


class ManifestoInvalido(Exception):
    pass


class SkillManifest:
    """Representação validada de um manifest.json de skill."""

    def __init__(self, dados, caminho):
        for campo in CAMPOS_OBRIGATORIOS:
            if not dados.get(campo):
                raise ManifestoInvalido(f"Campo obrigatório ausente em {caminho}: '{campo}'")

        self.nome = dados["nome"]
        self.descricao = dados["descricao"]
        self.versao = dados["versao"]
        self.autor = dados.get("autor", "desconhecido")
        self.permissoes = dados.get("permissoes", [])
        self.ferramentas = dados.get("ferramentas", [])
        self.intencoes = dados.get("intencoes", [])
        self.configuracao = dados.get("configuracao", {})
        self.dependencias = dados.get("dependencias", [])
        self.compatibilidade = dados.get("compatibilidade", {})
        self.offline = bool(dados.get("offline", True))
        self.caminho = caminho

    def para_dict(self):
        return {
            "nome": self.nome,
            "descricao": self.descricao,
            "versao": self.versao,
            "autor": self.autor,
            "permissoes": self.permissoes,
            "ferramentas": self.ferramentas,
            "intencoes": self.intencoes,
            "configuracao": self.configuracao,
            "dependencias": self.dependencias,
            "compatibilidade": self.compatibilidade,
            "offline": self.offline,
        }


class SkillRegistry:
    """
    Descobre skills em `pasta_skills` (uma subpasta por skill, cada
    uma com um manifest.json na raiz da subpasta).
    """

    def __init__(self, pasta_skills=None, caminho_estado=None):
        self.pasta_skills = pasta_skills or PASTA_SKILLS_PADRAO
        self.caminho_estado = caminho_estado or CAMINHO_ESTADO_PADRAO
        self._manifestos = {}
        self._ativas = None

    def descobrir(self):
        """
        (Re)lê todos os manifest.json encontrados. Nunca levanta
        exceção por causa de UMA skill malformada — registra o erro e
        continua com as demais (uma skill quebrada não pode travar a
        Beta inteira, ver item 31: "ao encontrar erro, corrigir
        imediatamente" — aqui o erro fica visível no console, mas
        isolado).
        """
        self._manifestos = {}
        if not os.path.isdir(self.pasta_skills):
            return self._manifestos

        for nome_pasta in sorted(os.listdir(self.pasta_skills)):
            caminho_manifesto = os.path.join(self.pasta_skills, nome_pasta, "manifest.json")
            if not os.path.isfile(caminho_manifesto):
                continue
            try:
                with open(caminho_manifesto, "r", encoding="utf-8") as arquivo:
                    dados = json.load(arquivo)
                manifesto = SkillManifest(dados, caminho_manifesto)
                self._manifestos[manifesto.nome] = manifesto
            except Exception as erro:
                print(f"[SKILLS] Manifesto inválido em {caminho_manifesto}: {erro}")

        return self._manifestos

    def listar(self):
        if not self._manifestos:
            self.descobrir()
        return list(self._manifestos.values())

    def obter(self, nome):
        if not self._manifestos:
            self.descobrir()
        return self._manifestos.get(nome)

    def _carregar_estado_ativacao(self):
        if self._ativas is not None:
            return self._ativas
        if os.path.exists(self.caminho_estado):
            try:
                with open(self.caminho_estado, "r", encoding="utf-8") as arquivo:
                    self._ativas = set(json.load(arquivo).get("ativas", []))
                    return self._ativas
            except Exception:
                pass
        # Padrão: toda skill descoberta começa ATIVA — preserva o
        # comportamento de sempre (word/excel/powerpoint disponíveis
        # sem precisar de nenhuma ativação manual); só fica desativada
        # se alguém desativar explicitamente.
        self._ativas = {m.nome for m in self.listar()}
        return self._ativas

    def _salvar_estado_ativacao(self):
        os.makedirs(os.path.dirname(self.caminho_estado), exist_ok=True)
        with open(self.caminho_estado, "w", encoding="utf-8") as arquivo:
            json.dump({"ativas": sorted(self._ativas)}, arquivo, ensure_ascii=False, indent=2)

    def esta_ativa(self, nome):
        return nome in self._carregar_estado_ativacao()

    def _registrar_evento_sync(self, tipo, nome):
        """Enfileira localmente para a BETA-CLOUD (ver memory/sync.py
        -> FASE 3) — best-effort: nunca impede ativar/desativar uma
        skill se a fila local falhar por qualquer motivo."""
        try:
            from memory import sync
            sync.enfileirar(tipo, {"skill": nome})
        except Exception:
            pass

    def ativar(self, nome):
        if self.obter(nome) is None:
            return False, f"Habilidade '{nome}' não encontrada."
        self._carregar_estado_ativacao().add(nome)
        self._salvar_estado_ativacao()
        self._registrar_evento_sync("SKILL_ENABLED", nome)
        return True, f"Habilidade '{nome}' ativada."

    def desativar(self, nome):
        if self.obter(nome) is None:
            return False, f"Habilidade '{nome}' não encontrada."
        self._carregar_estado_ativacao().discard(nome)
        self._salvar_estado_ativacao()
        self._registrar_evento_sync("SKILL_DISABLED", nome)
        return True, f"Habilidade '{nome}' desativada."
