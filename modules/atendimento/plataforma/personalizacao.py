"""Configuração completa por cliente, feita pelo RMD Desenvolvedor (sem acesso aos dados das pessoas).

Para cada igreja (Sede) o RMD Desenvolvedor define:
- o NOME de cada perfil (Administração da Sede, Pastor, Obreiro, Membro…);
- para cada perfil, quais TELAS do menu aparecem e quais AÇÕES (ver, criar, editar, excluir…) ficam liberadas;
- o NOME e a explicação de cada tela do menu;
- o CARTÃO DO VISITANTE (QR): abas, títulos, textos e cada campo (ligado, nome, obrigatório).

Segurança: o servidor confere tudo. A configuração só pode TIRAR permissões do padrão — nunca dar a um perfil
algo que a tabela de permissões não dá (assim ninguém ganha acesso a dados que não deveria por engano).
Aqui só ficam nomes e liga/desliga — nenhum dado de pessoa.
"""
from __future__ import annotations

import json

from . import permissoes
from .db import agora
from .nucleo import Ator, ErroNegocio

PERFIS_CONFIGURAVEIS = ("admin", "supervisor", "atendente", "cliente")
NOMES_PERFIS_IGREJA = {"admin": "Administração da Sede", "supervisor": "Pastor", "atendente": "Obreiro / Equipe",
                       "cliente": "Membro (portal)"}

NOMES_RECURSOS = {
    "dashboard": "Dashboard", "conversas": "Atendimento", "contatos": "Nomes", "filas": "Filas & Equipes",
    "orcamentos": "Solicitações", "servicos": "Tipos de solicitação", "fluxos": "Fluxos (robô)", "agenda": "Agenda",
    "whatsapp": "WhatsApp", "api": "API & Webhooks", "alertas": "Alertas", "relatorios": "Relatórios",
    "usuarios": "Usuários", "backup": "Backup", "plano": "Plano", "seguranca": "Segurança", "config": "Configurações",
    "portal": "Portal do membro", "visitantes": "Visitantes & Consolidação", "oracoes": "Pedidos de oração",
    "organizacao": "Organização", "valores": "Valores em dinheiro", "recepcao": "Recepção por roteiro",
}
NOMES_ACOES = {
    "ver": "ver", "criar": "criar", "editar": "editar", "excluir": "excluir (LGPD)", "responder": "responder",
    "atribuir": "atribuir", "encerrar": "encerrar", "enviar": "enviar", "publicar": "publicar", "simular": "simular",
    "configurar": "configurar", "testar": "testar", "marcar": "marcar como lido", "exportar": "exportar",
    "restaurar": "restaurar", "alterar": "alterar", "auditoria": "ver auditoria", "decidir_orcamento": "decidir solicitação",
    "mensagem": "mandar mensagem", "usar": "usar", "pastoral": "ver pedidos confidenciais (pastoral)",
}
# Ações que nunca são tiradas (a pessoa precisa delas para entrar e cuidar da própria conta).
ACOES_FIXAS = {("seguranca", "ver")}

CAMPOS_VISITANTE = (
    ("nome", "Seu nome", True, True),          # (campo, rótulo padrão, obrigatório padrão, fixo = não pode desligar)
    ("telefone", "WhatsApp", True, True),
    ("nascimento", "Aniversário", False, False),
    ("bairro", "Bairro", False, False),
    ("como_conheceu", "Como conheceu a igreja?", False, False),
    ("convidado_por", "Quem te convidou? (opcional)", False, False),
    ("quer_visita", "Gostaria de receber uma visita", False, False),
    ("pedido", "Quer deixar um pedido de oração? (opcional)", False, False),
)
CAMPOS_ORACAO = (
    ("pedido", "Seu pedido", True, True),
    ("categoria", "Assunto", False, False),
    ("privacidade", "Quem pode ver", False, False),
    ("nome", "Seu nome", False, False),
    ("telefone", "WhatsApp", False, False),
    ("anonimo", "Quero ficar anônimo", False, False),
    ("quer_contato", "Quero conversar com alguém", False, False),
)
TEXTOS_CARTAO = {
    "aba_visitante": "👋 Primeira vez aqui", "aba_oracao": "🙏 Pedido de oração",
    "texto_visitante": "Deixe seu contato para a igreja te conhecer melhor. Leva 1 minuto.",
    "texto_oracao": "Conte pelo que podemos orar. A equipe de intercessão vai orar por você.",
    "obrigado_visitante": "Que alegria ter você conosco! Em breve alguém da igreja vai falar com você.",
    "obrigado_oracao": "Recebemos o seu pedido. Vamos orar por você.",
    "subtitulo": "Que alegria ter você aqui!",
}


def _txt(valor, maximo: int = 80) -> str | None:
    t = " ".join(str(valor or "").split())[:maximo]
    return t or None


def _bool(valor) -> bool:
    return valor in (True, 1, "1", "true", "on", "sim")


def telas_padrao(perfil: str) -> list[str]:
    return [t for t in permissoes.telas_do_perfil(perfil, church=True) if t not in ("companies", "system")]


class PersonalizacaoMixin:
    # ------------------------------------------------------------------ leitura
    def obter_personalizacao(self, empresa_id: str | None) -> dict:
        if not empresa_id:
            return {}
        try:
            linha = self.banco.um("SELECT dados FROM empresa_personalizacao WHERE empresa_id=?", (empresa_id,))
        except Exception:  # noqa: BLE001 - banco antigo sem a tabela ainda
            return {}
        try:
            return json.loads(linha["dados"]) if linha else {}
        except ValueError:
            return {}

    def restricoes_do_perfil(self, empresa_id: str | None, perfil: str) -> tuple[set[str], set[str]]:
        """(recursos desligados para o perfil, ações desligadas 'recurso.acao') pela configuração da igreja."""
        conf = (self.obter_personalizacao(empresa_id).get("perfis") or {}).get(perfil) or {}
        recurso_da_tela = dict(permissoes.TELAS)
        recursos = {recurso_da_tela[t] for t, ligada in (conf.get("telas") or {}).items() if not ligada and t in recurso_da_tela}
        recursos.discard("seguranca")
        acoes = {f"{r}.{a}" for r, mapa in (conf.get("acoes") or {}).items() for a, ligada in (mapa or {}).items()
                 if not ligada and (r, a) not in ACOES_FIXAS}
        return recursos, acoes

    def nomes_personalizados(self, empresa_id: str | None) -> dict:
        """Só os nomes (para as telas mostrarem): perfis e itens do menu."""
        conf = self.obter_personalizacao(empresa_id)
        return {
            "perfis": {p: c["nome"] for p, c in (conf.get("perfis") or {}).items() if isinstance(c, dict) and c.get("nome")},
            "telas": {t: c for t, c in (conf.get("telas") or {}).items() if isinstance(c, dict) and (c.get("nome") or c.get("sub"))},
        }

    def cartao_publico(self, empresa_id: str) -> dict:
        """Como o cartão do visitante deve aparecer (página pública): abas, textos e campos."""
        conf = self.obter_personalizacao(empresa_id).get("cartao") or {}
        campos = conf.get("campos") or {}

        def montar(lista, tipo):
            saida = []
            for campo, rotulo, obrig, fixo in lista:
                c = (campos.get(tipo) or {}).get(campo) or {}
                ativo = True if fixo else c.get("ativo", True)
                if ativo:
                    saida.append({"campo": campo, "rotulo": c.get("rotulo") or rotulo,
                                  "obrigatorio": True if fixo and obrig else bool(c.get("obrigatorio", obrig))})
            return saida

        return {
            "visitante": conf.get("visitante", True), "oracao": conf.get("oracao", True),
            "textos": {k: (conf.get("textos") or {}).get(k) or v for k, v in TEXTOS_CARTAO.items()},
            "campos_visitante": montar(CAMPOS_VISITANTE, "visitante"),
            "campos_oracao": montar(CAMPOS_ORACAO, "oracao"),
        }

    # ------------------------------------------------------------------ área do RMD Desenvolvedor
    def catalogo_personalizacao(self, ator: Ator, empresa_id: str) -> dict:
        ator.exigir("empresas", "editar")
        self.obter_empresa(empresa_id)
        perfis = []
        for p in PERFIS_CONFIGURAVEIS:
            acoes = {}
            for recurso, mapa in permissoes.MATRIZ.items():
                if recurso in ("empresas",):
                    continue
                lista = [a for a, quem in mapa.items() if p in quem and (recurso, a) not in ACOES_FIXAS]
                if lista:
                    acoes[recurso] = lista
            perfis.append({"perfil": p, "nome_padrao": NOMES_PERFIS_IGREJA[p], "telas": telas_padrao(p), "acoes": acoes})
        todas = []
        for p in perfis:
            for t in p["telas"]:
                if t not in todas:
                    todas.append(t)
        return {
            "perfis": perfis,
            "telas": [{"tela": t, "recurso": dict(permissoes.TELAS)[t]} for t in todas],
            "nomes_recursos": NOMES_RECURSOS, "nomes_acoes": NOMES_ACOES,
            "cartao": {"textos": TEXTOS_CARTAO,
                       "campos_visitante": [{"campo": c, "rotulo": r, "obrigatorio": o, "fixo": f} for c, r, o, f in CAMPOS_VISITANTE],
                       "campos_oracao": [{"campo": c, "rotulo": r, "obrigatorio": o, "fixo": f} for c, r, o, f in CAMPOS_ORACAO]},
            "atual": self.obter_personalizacao(empresa_id),
        }

    def salvar_personalizacao(self, ator: Ator, empresa_id: str, dados: dict) -> dict:
        ator.exigir("empresas", "editar")
        self.obter_empresa(empresa_id)
        if not isinstance(dados, dict):
            raise ErroNegocio("Configuração inválida.")
        recurso_da_tela = dict(permissoes.TELAS)
        limpo: dict = {"perfis": {}, "telas": {}, "cartao": {}}
        for p in PERFIS_CONFIGURAVEIS:
            entrada = (dados.get("perfis") or {}).get(p) or {}
            padrao_telas = telas_padrao(p)
            telas = {t: _bool(v) for t, v in (entrada.get("telas") or {}).items() if t in padrao_telas and t != "security"}
            acoes = {}
            for r, mapa in (entrada.get("acoes") or {}).items():
                permitidas = permissoes.MATRIZ.get(r, {})
                if r == "empresas" or not isinstance(mapa, dict):
                    continue
                m = {a: _bool(v) for a, v in mapa.items() if p in permitidas.get(a, ()) and (r, a) not in ACOES_FIXAS}
                if m:
                    acoes[r] = m
            item = {"telas": {t: v for t, v in telas.items() if not v}, "acoes": {r: {a: v for a, v in m.items() if not v} for r, m in acoes.items()}}
            item["acoes"] = {r: m for r, m in item["acoes"].items() if m}
            nome = _txt(entrada.get("nome"), 60)
            if nome:
                item["nome"] = nome
            if nome or item["telas"] or item["acoes"]:
                limpo["perfis"][p] = item
        for t, c in (dados.get("telas") or {}).items():
            if t in recurso_da_tela and isinstance(c, dict):
                nome, sub = _txt(c.get("nome"), 50), _txt(c.get("sub"), 140)
                if nome or sub:
                    limpo["telas"][t] = {k: v for k, v in (("nome", nome), ("sub", sub)) if v}
        cartao = dados.get("cartao") or {}
        limpo["cartao"] = {"visitante": _bool(cartao.get("visitante", True)), "oracao": _bool(cartao.get("oracao", True)),
                           "textos": {}, "campos": {"visitante": {}, "oracao": {}}}
        if not limpo["cartao"]["visitante"] and not limpo["cartao"]["oracao"]:
            raise ErroNegocio("Deixe pelo menos uma aba do cartão ligada (visitante ou pedido de oração).")
        for k in TEXTOS_CARTAO:
            v = _txt((cartao.get("textos") or {}).get(k), 300)
            if v:
                limpo["cartao"]["textos"][k] = v
        for tipo, lista in (("visitante", CAMPOS_VISITANTE), ("oracao", CAMPOS_ORACAO)):
            for campo, _rotulo, obrig, fixo in lista:
                c = ((cartao.get("campos") or {}).get(tipo) or {}).get(campo)
                if not isinstance(c, dict):
                    continue
                item = {"ativo": True if fixo else _bool(c.get("ativo", True)),
                        "obrigatorio": True if fixo and obrig else _bool(c.get("obrigatorio", obrig))}
                rotulo = _txt(c.get("rotulo"), 80)
                if rotulo:
                    item["rotulo"] = rotulo
                limpo["cartao"]["campos"][tipo][campo] = item
        self.banco.executar(
            """INSERT INTO empresa_personalizacao(empresa_id, dados, atualizado_em) VALUES (?,?,?)
               ON CONFLICT(empresa_id) DO UPDATE SET dados=excluded.dados, atualizado_em=excluded.atualizado_em""",
            (empresa_id, json.dumps(limpo, ensure_ascii=False), agora()))
        self.auditar(ator, "sistema.personalizacao", empresa_id, None, empresa_id=empresa_id)
        return self.catalogo_personalizacao(ator, empresa_id)

    # ------------------------------------------------------------------ cartão: confere o que a pessoa mandou
    def conferir_cartao(self, empresa_id: str, dados: dict) -> dict:
        """Aplica a configuração do cartão: aba desligada é recusada, campo desligado é ignorado, obrigatório é exigido."""
        conf = self.cartao_publico(empresa_id)
        tipo = dados.get("tipo") or "visitante"
        if tipo not in ("visitante", "oracao") or not conf["oracao" if tipo == "oracao" else "visitante"]:
            raise ErroNegocio("Esta parte do cartão não está disponível.")
        campos = conf["campos_oracao" if tipo == "oracao" else "campos_visitante"]
        ligados = {c["campo"] for c in campos}
        lista = CAMPOS_ORACAO if tipo == "oracao" else CAMPOS_VISITANTE
        limpo = {k: v for k, v in dados.items() if k not in {c for c, *_ in lista} or k in ligados}
        if tipo == "visitante" and "pedido" not in ligados:
            limpo.pop("categoria", None)
        for c in campos:
            if c["obrigatorio"] and not str(limpo.get(c["campo"]) or "").strip() and limpo.get(c["campo"]) is not True:
                raise ErroNegocio(f"Preencha: {c['rotulo']}.")
        return limpo
