"""Cargos da igreja (pastor, presbítero, diácono, evangelista, tesoureiro(a), zelador(a)…).

O cargo fica na ficha de cada pessoa que usa o sistema e faz parte do que ela pode ver e fazer:
- o NÍVEL do cargo (0 a 100) mostra a hierarquia e fica disponível para regras do sistema — ter nível maior
  NÃO dá, sozinho, acesso a nada;
- a TABELA de permissões do cargo diz o que fica DESLIGADO para quem tem aquele cargo (telas e ações).

Segurança: a tabela do cargo só TIRA permissões do perfil da pessoa; nunca dá algo que o perfil não tem.
O servidor confere tudo (a tela só esconde botões).
"""
from __future__ import annotations

import json

from . import permissoes
from .db import agora
from .nucleo import Ator, ErroNegocio, NaoEncontrado, _texto, novo_id
from .personalizacao import ACOES_FIXAS, NOMES_ACOES, NOMES_RECURSOS

# (nome, nível, ações/recursos desligados de início). A igreja pode renomear, criar, apagar e mudar tudo.
_SEM_FINANCEIRO = {"recursos": {"valores": False, "relatorios": False}, "acoes": {"oracoes": {"pastoral": False}}}
CARGOS_PADRAO = (
    ("Pastor presidente", 100, {}),
    ("Pastor", 90, {}),
    ("Pastor auxiliar", 85, {}),
    ("Evangelista", 75, {}),
    ("Missionário(a)", 70, {}),
    ("Presbítero", 65, {}),
    ("Diácono / Diaconisa", 55, {}),
    ("Tesoureiro(a)", 50, {"acoes": {"oracoes": {"pastoral": False}}}),
    ("Secretário(a)", 50, {"acoes": {"oracoes": {"pastoral": False}}}),
    ("Líder de ministério / departamento", 45, {}),
    ("Cooperador(a)", 40, {}),
    ("Obreiro(a)", 40, {}),
    ("Professor(a) de Escola Bíblica", 35, _SEM_FINANCEIRO),
    ("Líder de louvor / músico", 35, _SEM_FINANCEIRO),
    ("Porteiro(a) / recepção", 30, _SEM_FINANCEIRO),
    ("Zelador(a)", 30, _SEM_FINANCEIRO),
    ("Auxiliar", 25, _SEM_FINANCEIRO),
    ("Membro", 10, _SEM_FINANCEIRO),
    ("Congregado(a)", 5, _SEM_FINANCEIRO),
)
RECURSOS_FORA = ("empresas", "portal", "recepcao")


def _limpar_restricoes(entrada) -> dict:
    """Guarda só o que está DESLIGADO e que realmente existe na tabela de permissões."""
    entrada = entrada if isinstance(entrada, dict) else {}
    saida: dict = {"recursos": {}, "acoes": {}}
    for r, ligado in (entrada.get("recursos") or {}).items():
        if r in permissoes.MATRIZ and r not in RECURSOS_FORA and r != "seguranca" and ligado in (False, 0, "0", "false"):
            saida["recursos"][r] = False
    for r, mapa in (entrada.get("acoes") or {}).items():
        if r not in permissoes.MATRIZ or r in RECURSOS_FORA or not isinstance(mapa, dict):
            continue
        m = {a: False for a, ligado in mapa.items()
             if a in permissoes.MATRIZ[r] and (r, a) not in ACOES_FIXAS and ligado in (False, 0, "0", "false")}
        if m:
            saida["acoes"][r] = m
    return {k: v for k, v in saida.items() if v}


class CargosMixin:
    # ------------------------------------------------------------------ base
    def _garantir_cargos(self, empresa_id: str) -> None:
        if self.banco.um("SELECT 1 AS x FROM igreja_cargos WHERE empresa_id=?", (empresa_id,)):
            return
        with self.banco.transacao() as c:
            for ordem, (nome, nivel, restr) in enumerate(CARGOS_PADRAO):
                c.execute("INSERT INTO igreja_cargos(id, empresa_id, nome, nivel, ordem, ativo, restricoes, criado_em) VALUES (?,?,?,?,?,1,?,?)",
                          (novo_id(), empresa_id, nome, nivel, ordem, json.dumps(_limpar_restricoes(restr), ensure_ascii=False), agora()))

    def info_cargo(self, cargo_id: str) -> dict:
        c = self.banco.um("SELECT id, nome, nivel FROM igreja_cargos WHERE id=?", (cargo_id,))
        return c or {}

    def restricoes_do_cargo(self, empresa_id: str | None, cargo_id: str | None) -> tuple[set[str], set[str]]:
        """(recursos desligados, ações desligadas 'recurso.acao') para quem tem esse cargo."""
        if not empresa_id or not cargo_id:
            return set(), set()
        linha = self.banco.um("SELECT restricoes FROM igreja_cargos WHERE id=? AND empresa_id=? AND ativo=1", (cargo_id, empresa_id))
        if not linha:
            return set(), set()
        try:
            r = json.loads(linha["restricoes"] or "{}")
        except ValueError:
            return set(), set()
        recursos = {x for x, ligado in (r.get("recursos") or {}).items() if not ligado and x != "seguranca"}
        acoes = {f"{x}.{a}" for x, mapa in (r.get("acoes") or {}).items() for a, ligado in (mapa or {}).items()
                 if not ligado and (x, a) not in ACOES_FIXAS}
        return recursos, acoes

    # ------------------------------------------------------------------ telas
    def catalogo_cargos(self) -> list[dict]:
        """O que dá para ligar/desligar por cargo: cada função do sistema e suas ações."""
        itens = []
        for recurso, mapa in permissoes.MATRIZ.items():
            if recurso in RECURSOS_FORA or recurso == "seguranca":
                continue
            itens.append({"recurso": recurso, "nome": NOMES_RECURSOS.get(recurso, recurso),
                          "acoes": [{"acao": a, "nome": NOMES_ACOES.get(a, a)} for a in mapa if (recurso, a) not in ACOES_FIXAS]})
        return itens

    def listar_cargos(self, ator: Ator) -> list[dict]:
        ator.exigir("usuarios", "ver")
        self._garantir_cargos(ator.empresa)
        linhas = self.banco.todos(
            """SELECT g.*, (SELECT COUNT(*) FROM usuarios u WHERE u.cargo_id=g.id AND u.ativo=1) AS pessoas
               FROM igreja_cargos g WHERE g.empresa_id=? ORDER BY g.nivel DESC, g.ordem, g.nome""", (ator.empresa,))
        for g in linhas:
            try:
                g["restricoes"] = json.loads(g["restricoes"] or "{}")
            except ValueError:
                g["restricoes"] = {}
        return linhas

    def salvar_cargo(self, ator: Ator, dados: dict, cargo_id: str | None = None) -> dict:
        ator.exigir("usuarios", "editar")
        self._garantir_cargos(ator.empresa)
        dados = dados if isinstance(dados, dict) else {}
        atual = None
        if cargo_id:
            atual = self.banco.um("SELECT * FROM igreja_cargos WHERE id=? AND empresa_id=?", (cargo_id, ator.empresa))
            if not atual:
                raise NaoEncontrado("Cargo não encontrado.")
        nome = _texto(dados.get("nome", atual["nome"] if atual else None), "nome do cargo", maximo=60)
        try:
            nivel = int(dados.get("nivel", atual["nivel"] if atual else 0))
        except (TypeError, ValueError):
            raise ErroNegocio("O nível do cargo é um número de 0 a 100.") from None
        nivel = max(0, min(100, nivel))
        if self.banco.um("SELECT 1 AS x FROM igreja_cargos WHERE empresa_id=? AND nome=? COLLATE NOCASE AND id<>?", (ator.empresa, nome, cargo_id or "")):
            raise ErroNegocio("Já existe um cargo com esse nome.")
        ativo = 1 if dados.get("ativo", atual["ativo"] if atual else 1) in (True, 1, "1", "true") else 0
        if "restricoes" in dados:
            restricoes = _limpar_restricoes(dados.get("restricoes"))
        else:
            restricoes = json.loads(atual["restricoes"] or "{}") if atual else {}
        texto = json.dumps(restricoes, ensure_ascii=False)
        if atual:
            self.banco.executar("UPDATE igreja_cargos SET nome=?, nivel=?, ativo=?, restricoes=? WHERE id=?", (nome, nivel, ativo, texto, cargo_id))
        else:
            cargo_id = novo_id()
            ordem = (self.banco.um("SELECT COALESCE(MAX(ordem),0)+1 AS o FROM igreja_cargos WHERE empresa_id=?", (ator.empresa,)) or {"o": 1})["o"]
            self.banco.executar("INSERT INTO igreja_cargos(id, empresa_id, nome, nivel, ordem, ativo, restricoes, criado_em) VALUES (?,?,?,?,?,?,?,?)",
                                (cargo_id, ator.empresa, nome, nivel, ordem, ativo, texto, agora()))
        self.auditar(ator, "cargo.salvar", cargo_id, {"nome": nome, "nivel": nivel})
        return next(g for g in self.listar_cargos(ator) if g["id"] == cargo_id)

    def excluir_cargo(self, ator: Ator, cargo_id: str) -> dict:
        ator.exigir("usuarios", "editar")
        cargo = self.banco.um("SELECT * FROM igreja_cargos WHERE id=? AND empresa_id=?", (cargo_id, ator.empresa))
        if not cargo:
            raise NaoEncontrado("Cargo não encontrado.")
        em_uso = self.banco.um("SELECT COUNT(*) AS n FROM usuarios WHERE cargo_id=?", (cargo_id,))["n"]
        if em_uso:
            raise ErroNegocio(f"{em_uso} pessoa(s) têm este cargo. Troque o cargo delas antes de apagar (ou desligue o cargo).")
        self.banco.executar("DELETE FROM igreja_cargos WHERE id=?", (cargo_id,))
        self.auditar(ator, "cargo.excluir", cargo_id, {"nome": cargo["nome"]})
        return {"ok": True}
