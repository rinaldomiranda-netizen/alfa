"""Nomes repetidos: evita cadastrar a mesma pessoa duas vezes (mesmo telefone ou mesmo nome).

- Ao cadastrar/editar, se já existe alguém com o mesmo telefone/WhatsApp ou o mesmo nome, o sistema NÃO grava:
  devolve a lista de parecidos (com o mais completo em primeiro) e pergunta o que fazer.
- "Mesclar" junta os dois: fica o cadastro escolhido, os campos vazios são completados com os dados do outro,
  e conversas, orçamentos, agenda, pedidos de oração e jornada passam para o que fica.
- Mesmo telefone = mesma pessoa (só dá para mesclar). Só o mesmo nome (telefone diferente) pode ser "pessoas diferentes".
"""
from __future__ import annotations

import json
import unicodedata

from .db import agora
from .nucleo import Ator, Conflito, ErroNegocio, NaoEncontrado


class Duplicidade(Conflito):
    """409 com a lista de cadastros parecidos para a pessoa escolher."""

    def __init__(self, mensagem: str, candidatos: list[dict], pode_criar: bool):
        super().__init__(mensagem)
        self.candidatos = candidatos
        self.pode_criar = pode_criar


def chave_nome(nome: str | None) -> str:
    texto = unicodedata.normalize("NFKD", nome or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split())


def _vazio(v) -> bool:
    return v is None or str(v).strip() in ("", "[]", "{}")


class DuplicidadeMixin:
    # ------------------------------------------------------------ completude
    def _pontos_contato(self, c: dict) -> int:
        pontos = 0
        for campo in ("telefone", "whatsapp", "email", "observacoes"):
            if not _vazio(c.get(campo)):
                pontos += 2
        if not _vazio(c.get("tags")):
            pontos += 1
        if not _vazio(c.get("dados")):
            pontos += 1
        pontos += min(5, self.banco.um("SELECT COUNT(*) AS n FROM conversas WHERE contato_id=?", (c["id"],))["n"])
        if self.banco.um("SELECT 1 AS x FROM igreja_jornada WHERE contato_id=?", (c["id"],)):
            pontos += 2
        if c.get("status") == "inativo" or str(c.get("nome", "")).startswith("Nome removido"):
            pontos -= 3
        return pontos

    def _candidato(self, c: dict, motivo: str) -> dict:
        pub = self._contato_publico(c)
        pub["pontos"] = self._pontos_contato(c)
        pub["motivo"] = motivo
        return pub

    # ------------------------------------------------------------ busca
    def _achar_parecidos(self, empresa_id: str, nome: str, telefones: list[str], ignorar: str | None = None) -> list[dict]:
        achados: dict[str, tuple[dict, str]] = {}
        linhas = self.banco.todos("SELECT * FROM contatos WHERE empresa_id=? AND nome NOT LIKE 'Nome removido%'", (empresa_id,))
        tels = {t for t in telefones if t}
        chave = chave_nome(nome)
        for c in linhas:
            if c["id"] == ignorar:
                continue
            if tels and ({c.get("telefone"), c.get("whatsapp")} & tels):
                achados[c["id"]] = (c, "telefone")
            elif chave and chave_nome(c["nome"]) == chave:
                achados[c["id"]] = (c, "nome")
        res = [self._candidato(c, m) for c, m in achados.values()]
        res.sort(key=lambda x: -x["pontos"])
        return res

    def _checar_duplicidade(self, empresa_id: str, valores: dict, ignorar: str | None = None) -> None:
        parecidos = self._achar_parecidos(empresa_id, valores["nome"], [valores["telefone"], valores["whatsapp"]], ignorar)
        if not parecidos:
            return
        mesmo_tel = any(p["motivo"] == "telefone" for p in parecidos)
        msg = ("Já existe cadastro com esse telefone/WhatsApp." if mesmo_tel
               else "Já existe alguém com esse mesmo nome.") + " Escolha qual manter."
        raise Duplicidade(msg, parecidos, pode_criar=not mesmo_tel)

    # ------------------------------------------------------------ varredura
    def listar_duplicados(self, ator: Ator) -> list[dict]:
        ator.exigir("contatos", "ver")
        linhas = [c for c in self.banco.todos(
            "SELECT * FROM contatos WHERE empresa_id=? AND nome NOT LIKE 'Nome removido%'", (ator.empresa,))
            if self._contato_no_alcance(ator, c)]
        pai = {c["id"]: c["id"] for c in linhas}

        def raiz(x):
            while pai[x] != x:
                pai[x] = pai[pai[x]]
                x = pai[x]
            return x

        def unir(a, b):
            pai[raiz(a)] = raiz(b)

        por_chave: dict[str, str] = {}
        for c in linhas:
            for k in {"t:" + str(c.get("telefone") or ""), "t:" + str(c.get("whatsapp") or ""), "n:" + chave_nome(c["nome"])}:
                if k in ("t:", "t:None", "n:"):
                    continue
                if k in por_chave:
                    unir(c["id"], por_chave[k])
                else:
                    por_chave[k] = c["id"]
        grupos: dict[str, list[dict]] = {}
        for c in linhas:
            grupos.setdefault(raiz(c["id"]), []).append(c)
        saida = []
        for membros in grupos.values():
            if len(membros) < 2:
                continue
            itens = [self._candidato(c, "") for c in membros]
            itens.sort(key=lambda x: -x["pontos"])
            saida.append({"sugerido": itens[0]["id"], "itens": itens})
        saida.sort(key=lambda g: g["itens"][0]["nome"].lower())
        return saida

    # ------------------------------------------------------------ mesclar
    def mesclar_contatos(self, ator: Ator, manter_id: str, remover_id: str) -> dict:
        ator.exigir("contatos", "editar")
        if manter_id == remover_id:
            raise ErroNegocio("Escolha dois cadastros diferentes.")
        a = self.banco.um("SELECT * FROM contatos WHERE id=? AND empresa_id=?", (manter_id, ator.empresa))
        b = self.banco.um("SELECT * FROM contatos WHERE id=? AND empresa_id=?", (remover_id, ator.empresa))
        if not a or not b or not self._contato_no_alcance(ator, a) or not self._contato_no_alcance(ator, b):
            raise NaoEncontrado("Nome não encontrado.")
        novo = {}
        for campo in ("telefone", "whatsapp", "email"):
            if _vazio(a.get(campo)) and not _vazio(b.get(campo)):
                novo[campo] = b[campo]
        obs_a, obs_b = (a.get("observacoes") or "").strip(), (b.get("observacoes") or "").strip()
        if obs_b and obs_b not in obs_a:
            novo["observacoes"] = (obs_a + "\n" + obs_b).strip()[:2000]
        tags = sorted(set(json.loads(a.get("tags") or "[]")) | set(json.loads(b.get("tags") or "[]")))[:15]
        novo["tags"] = json.dumps(tags, ensure_ascii=False)
        dados = {**json.loads(b.get("dados") or "{}"), **json.loads(a.get("dados") or "{}")}
        novo["dados"] = json.dumps(dados, ensure_ascii=False)
        ult = max([x for x in (a.get("ultimo_contato"), b.get("ultimo_contato")) if x], default=None)
        novo["ultimo_contato"] = ult
        if a.get("status") == "novo" and b.get("status") == "ativo":
            novo["status"] = "ativo"
        with self.banco.transacao() as c:
            # libera o telefone do que sai antes de passar para o que fica (evita choque de únicos)
            for t in ("conversas", "orcamentos", "agenda", "igreja_oracoes", "usuarios"):
                c.execute(f"UPDATE {t} SET contato_id=? WHERE contato_id=?", (manter_id, remover_id))
            if c.execute("SELECT 1 FROM igreja_jornada WHERE contato_id=?", (manter_id,)).fetchone():
                c.execute("DELETE FROM igreja_jornada WHERE contato_id=?", (remover_id,))
            else:
                c.execute("UPDATE igreja_jornada SET contato_id=? WHERE contato_id=?", (manter_id, remover_id))
            c.execute("DELETE FROM contatos WHERE id=?", (remover_id,))
            partes = ", ".join(f"{k}=?" for k in novo)
            c.execute(f"UPDATE contatos SET {partes} WHERE id=?", [*novo.values(), manter_id])
        self.auditar(ator, "contato.mesclar", manter_id, detalhe={"removido": remover_id})
        return self.obter_contato(ator, manter_id)

    # ------------------------------------------------------------ ações na criação
    def _resolver_duplicidade_criacao(self, ator: Ator, dados: dict, valores: dict) -> dict | None:
        """Devolve o contato resultante se a pessoa escolheu uma ação; None = seguir criando."""
        dec = dados.get("duplicidade")
        if not isinstance(dec, dict):
            self._checar_duplicidade(ator.empresa, valores)
            return None
        acao, alvo = dec.get("acao"), dec.get("id")
        if acao == "criar":
            parecidos = self._achar_parecidos(ator.empresa, valores["nome"], [valores["telefone"], valores["whatsapp"]])
            if any(p["motivo"] == "telefone" for p in parecidos):
                raise ErroNegocio("Mesmo telefone é a mesma pessoa: escolha qual manter.")
            return None
        if acao in ("manter", "atualizar"):
            existente = self.banco.um("SELECT * FROM contatos WHERE id=? AND empresa_id=?", (alvo, ator.empresa))
            if not existente:
                raise NaoEncontrado("Nome não encontrado.")
            if acao == "manter":  # fica o que já existe, só completa o que estava vazio
                base = {k: existente.get(k) for k in ("nome", "telefone", "whatsapp", "email", "observacoes", "status")}
                for k in ("telefone", "whatsapp", "email", "observacoes"):
                    if _vazio(base[k]) and not _vazio(valores.get(k)):
                        base[k] = valores[k]
                tags = sorted(set(json.loads(existente.get("tags") or "[]")) | set(json.loads(valores["tags"])))[:15]
                base["tags"] = tags
                return self.editar_contato(ator, alvo, {**base, "_sem_duplicidade": True})
            return self.editar_contato(ator, alvo, {**{k: v for k, v in valores.items() if not _vazio(v)},
                                                    "tags": json.loads(valores["tags"]), "_sem_duplicidade": True})
        raise ErroNegocio("Escolha uma opção válida.")
