"""Financeiro (GMV, taxas, repasses, conciliação), doações com cadeia completa de confirmação e impacto."""
from __future__ import annotations

from .nucleo import Ator, ErroNegocio, NaoEncontrado, SemPermissao, inteiro, normalizar_data, novo_id, texto
from .ofertas import disponivel
from .pedidos import ESTADOS_FATURADOS

ESTADOS_DOACAO = {"proposta": "Proposta enviada", "aceita": "Aceita pela instituição", "recusada": "Recusada",
                  "coletada": "Coletada", "destinada": "Destinada (confirmada)", "cancelada": "Cancelada"}


def _periodo(de, ate) -> tuple[str, str]:
    i = normalizar_data(de) or "2000-01-01T00:00:00+00:00"
    f = normalizar_data(ate) or "2999-01-01T00:00:00+00:00"
    return i, f


class FinanceiroMixin:
    # ================================================================ FINANCEIRO
    def _escopo_fin(self, ator: Ator, empresa_id):
        ator.exigir("financeiro", "ver")
        if ator.plataforma and not empresa_id:
            return "", ()
        return " AND p.empresa_id=?", (ator.empresa_alvo(empresa_id),)

    def resumo_financeiro(self, ator: Ator, empresa_id: str | None = None, de=None, ate=None) -> dict:
        cond, par = self._escopo_fin(ator, empresa_id)
        i, f = _periodo(de, ate)
        fat = ",".join("?" * len(ESTADOS_FATURADOS))
        r = self.banco.um(f"""SELECT COUNT(*) AS pedidos, COALESCE(SUM(total_centavos),0) AS gmv, COALESCE(SUM(subtotal_centavos),0) AS produtos,
                                     COALESCE(SUM(normal_centavos),0) AS normal, COALESCE(SUM(taxa_centavos),0) AS taxa,
                                     COALESCE(SUM(repasse_centavos),0) AS repasse, COALESCE(SUM(entrega_centavos),0) AS entrega,
                                     COALESCE(SUM(CASE WHEN repasse_id IS NULL THEN repasse_centavos ELSE 0 END),0) AS a_repassar
                              FROM pedidos p WHERE p.status IN ({fat}) AND p.criado_em>=? AND p.criado_em<? {cond}""",
                          (*ESTADOS_FATURADOS, i, f, *par))
        andamento = self.banco.um(f"""SELECT COUNT(*) AS n, COALESCE(SUM(total_centavos),0) AS v FROM pedidos p
                                      WHERE p.status IN ('pago','recebido','preparando','pronto','aguardando_retirada','aguardando_entregador',
                                      'entregador_designado','em_coleta','em_rota','entregue','retirado') AND p.criado_em>=? AND p.criado_em<? {cond}""",
                                  (i, f, *par))
        por_empresa = self.banco.todos(f"""SELECT e.id, e.nome, COUNT(*) AS pedidos, SUM(p.subtotal_centavos) AS produtos,
                                                  SUM(p.taxa_centavos) AS taxa, SUM(p.repasse_centavos) AS repasse
                                           FROM pedidos p JOIN empresas e ON e.id=p.empresa_id
                                           WHERE p.status IN ({fat}) AND p.criado_em>=? AND p.criado_em<? {cond}
                                           GROUP BY e.id ORDER BY produtos DESC""", (*ESTADOS_FATURADOS, i, f, *par))
        return {"pedidos": r["pedidos"], "gmv_centavos": r["gmv"], "produtos_centavos": r["produtos"],
                "economia_clientes_centavos": r["normal"] - r["produtos"], "receita_parceiros_centavos": r["repasse"],
                "receita_plataforma_centavos": r["taxa"], "custo_entrega_centavos": r["entrega"],
                "a_repassar_centavos": r["a_repassar"], "em_andamento": andamento, "por_empresa": por_empresa,
                "aviso": "Pagamentos em MODO TESTE: nenhum dinheiro real foi movimentado."}

    def calcular_repasse(self, ator: Ator, empresa_id: str, de=None, ate=None) -> dict:
        ator.exigir("financeiro", "repassar")
        if not ator.plataforma:
            raise SemPermissao("Só a equipe Sobrou+ calcula repasses.")
        eid = ator.empresa_alvo(empresa_id)
        i, f = _periodo(de, ate)
        fat = ",".join("?" * len(ESTADOS_FATURADOS))
        with self.banco.transacao() as c:
            linhas = [dict(r) for r in c.execute(f"""SELECT id, subtotal_centavos, taxa_centavos, repasse_centavos FROM pedidos
                                                     WHERE empresa_id=? AND status IN ({fat}) AND repasse_id IS NULL AND criado_em>=? AND criado_em<?""",
                                                 (eid, *ESTADOS_FATURADOS, i, f)).fetchall()]
            if not linhas:
                raise ErroNegocio("Nenhum pedido concluído sem repasse neste período.")
            rid = novo_id()
            c.execute("""INSERT INTO repasses(id, empresa_id, periodo_inicio, periodo_fim, pedidos, bruto_centavos, taxa_centavos, valor_centavos,
                         status, criado_por, criado_em) VALUES (?,?,?,?,?,?,?,?,'calculado',?,?)""",
                      (rid, eid, i, f, len(linhas), sum(x["subtotal_centavos"] for x in linhas), sum(x["taxa_centavos"] for x in linhas),
                       sum(x["repasse_centavos"] for x in linhas), ator.usuario_id, self.agora()))
            for x in linhas:
                c.execute("UPDATE pedidos SET repasse_id=? WHERE id=?", (rid, x["id"]))
        self.auditar(ator, "repasse.calcular", rid, {"pedidos": len(linhas)}, empresa_id=eid)
        return self.banco.um("SELECT * FROM repasses WHERE id=?", (rid,))

    def marcar_repasse_pago(self, ator: Ator, repasse_id: str, referencia: str) -> dict:
        ator.exigir("financeiro", "repassar")
        if not ator.plataforma:
            raise SemPermissao("Só a equipe Sobrou+ registra repasses pagos.")
        r = ator.conferir_empresa(self.banco.um("SELECT * FROM repasses WHERE id=?", (repasse_id,)), "Repasse")
        if r["status"] == "pago":
            raise ErroNegocio("Este repasse já está marcado como pago.")
        ref = texto(referencia, 120, True, "o comprovante/referência da transferência")
        self.banco.executar("UPDATE repasses SET status='pago', pago_em=?, referencia=? WHERE id=?", (self.agora(), ref, repasse_id))
        self.auditar(ator, "repasse.pago", repasse_id, {"referencia": ref}, empresa_id=r["empresa_id"])
        self.avisar("Repasse registrado como pago pela equipe Sobrou+.", empresa_id=r["empresa_id"], papel_alvo="admin_empresa")
        return self.banco.um("SELECT * FROM repasses WHERE id=?", (repasse_id,))

    def listar_repasses(self, ator: Ator, empresa_id: str | None = None) -> list[dict]:
        ator.exigir("financeiro", "ver")
        if ator.plataforma and not empresa_id:
            return self.banco.todos("SELECT r.*, e.nome AS empresa FROM repasses r JOIN empresas e ON e.id=r.empresa_id ORDER BY r.criado_em DESC")
        return self.banco.todos("SELECT r.*, e.nome AS empresa FROM repasses r JOIN empresas e ON e.id=r.empresa_id WHERE r.empresa_id=? ORDER BY r.criado_em DESC",
                                (ator.empresa_alvo(empresa_id),))

    def conciliacao(self, ator: Ator, empresa_id: str | None = None) -> dict:
        """Confere pagamento × pedido × repasse. Lista toda divergência; não corrige nada sozinho."""
        cond, par = self._escopo_fin(ator, empresa_id)
        divergencias = []
        for p in self.banco.todos(f"""SELECT p.id, p.numero, p.status, p.total_centavos,
                                             (SELECT COALESCE(SUM(valor_centavos),0) FROM pagamentos g WHERE g.pedido_id=p.id AND g.status='aprovado') AS pago,
                                             (SELECT COUNT(*) FROM pagamentos g WHERE g.pedido_id=p.id AND g.status='estornado') AS estornos
                                      FROM pedidos p WHERE p.status NOT IN ('criado','aguardando_pagamento','expirado') {cond}""", par):
            if p["status"] == "cancelado":
                if p["pago"]:
                    divergencias.append({**p, "problema": "Pedido cancelado com pagamento ainda aprovado (falta estorno)."})
            elif p["pago"] != p["total_centavos"]:
                divergencias.append({**p, "problema": f"Pago {p['pago']} ≠ total do pedido {p['total_centavos']} (centavos)."})
        for r in self.banco.todos(f"""SELECT r.id, r.valor_centavos, r.status,
                                             (SELECT COALESCE(SUM(repasse_centavos),0) FROM pedidos p WHERE p.repasse_id=r.id) AS soma
                                      FROM repasses r WHERE 1=1 {cond.replace('p.empresa_id', 'r.empresa_id')}""", par):
            if r["soma"] != r["valor_centavos"]:
                divergencias.append({"id": r["id"], "problema": f"Repasse {r['valor_centavos']} ≠ soma dos pedidos {r['soma']}."})
        tot = self.banco.um(f"""SELECT COALESCE(SUM(g.valor_centavos),0) AS recebido FROM pagamentos g JOIN pedidos p ON p.id=g.pedido_id
                                WHERE g.status='aprovado' {cond}""", par)
        fat = self.banco.um(f"""SELECT COALESCE(SUM(taxa_centavos+repasse_centavos+entrega_centavos),0) AS distribuido FROM pedidos p
                                WHERE p.status NOT IN ('criado','aguardando_pagamento','expirado','cancelado') {cond}""", par)
        return {"recebido_centavos": tot["recebido"], "distribuido_centavos": fat["distribuido"],
                "fecha": tot["recebido"] == fat["distribuido"] and not divergencias, "divergencias": divergencias,
                "aviso": "Conciliação sobre pagamentos de TESTE. Extrato bancário real: BLOQUEADO POR DEPENDÊNCIA."}

    # ================================================================ DOAÇÕES
    def propor_doacao(self, ator: Ator, dados: dict) -> dict:
        """Sobra de oferta (encerrada ou ativa) ou pedido não retirado → instituição AUTORIZADA."""
        ator.exigir("doacoes", "propor")
        inst = self.banco.um("SELECT * FROM instituicoes WHERE id=?", (dados.get("instituicao_id"),))
        if not inst:
            raise ErroNegocio("Escolha a instituição.")
        if not inst["autorizada"]:
            raise ErroNegocio("Esta instituição ainda não foi autorizada pela equipe Sobrou+.")
        with self.banco.transacao() as c:
            if dados.get("pedido_id"):
                p = ator.conferir_empresa(self._uma(c, "SELECT * FROM pedidos WHERE id=?", (dados["pedido_id"],)), "Pedido")
                if p["status"] != "nao_retirado":
                    raise ErroNegocio("Só pedidos não retirados podem ser destinados para doação.")
                if self._uma(c, "SELECT id FROM doacoes WHERE pedido_id=? AND status NOT IN ('recusada','cancelada')", (p["id"],)):
                    raise ErroNegocio("Este pedido já tem doação em andamento.")
                qtd = self._uma(c, "SELECT SUM(quantidade) AS n FROM pedido_itens WHERE pedido_id=?", (p["id"],))["n"]
                eid, oferta_id, peso, origem = p["empresa_id"], None, p["peso_kg"], "pedido"
                desc = f"Pedido #{p['numero']} não retirado"
            else:
                o = ator.conferir_empresa(self._uma(c, "SELECT * FROM ofertas WHERE id=?", (dados.get("oferta_id"),)), "Oferta")
                qtd = inteiro(dados.get("quantidade"), "a quantidade", 1)
                if o["status"] == "encerrada":
                    if qtd > o["expirada"]:
                        raise ErroNegocio(f"Só sobraram {o['expirada']} unidades desta oferta.")
                    c.execute("UPDATE ofertas SET expirada=expirada-?, destinada=destinada+? WHERE id=?", (qtd, qtd, o["id"]))
                else:
                    if qtd > disponivel(o):
                        raise ErroNegocio(f"Só há {disponivel(o)} disponíveis.")
                    c.execute("UPDATE ofertas SET destinada=destinada+? WHERE id=?", (qtd, o["id"]))
                    self._atualizar_esgotada(c, o["id"])
                self._movimento(c, o["id"], o["empresa_id"], "doacao", qtd, ator, motivo=f"proposta para {inst['nome']}")
                eid, oferta_id, peso, origem = o["empresa_id"], o["id"], round(o["peso_kg_unidade"] * qtd, 3), "oferta"
                desc = o["nome"]
            did = novo_id()
            c.execute("""INSERT INTO doacoes(id, empresa_id, oferta_id, pedido_id, origem, instituicao_id, quantidade, peso_kg, descricao,
                         status, proposta_por, proposta_em, nota) VALUES (?,?,?,?,?,?,?,?,?,'proposta',?,?,?)""",
                      (did, eid, oferta_id, dados.get("pedido_id"), origem, inst["id"], qtd, peso,
                       texto(dados.get("descricao"), 300) or desc, ator.usuario_id, self.agora(), texto(dados.get("nota"), 300)))
            for u in c.execute("SELECT id FROM usuarios WHERE instituicao_id=? AND ativo=1", (inst["id"],)).fetchall():
                self.avisar(f"Nova doação oferecida: {desc} ({qtd} un., {peso:g} kg). Aceite ou recuse.", usuario_id=u["id"], conn=c)
        self.auditar(ator, "doacao.propor", did, {"instituicao": inst["id"], "quantidade": qtd}, empresa_id=eid)
        return self.obter_doacao(ator, did)

    def _doacao_visivel(self, ator: Ator, d: dict | None) -> dict:
        if not d:
            raise NaoEncontrado("Doação não encontrada.")
        if ator.papel == "instituicao":
            if d["instituicao_id"] != ator.instituicao_id:
                raise NaoEncontrado("Doação não encontrada.")
            return d
        ator.exigir("doacoes", "ver")
        return ator.conferir_empresa(d, "Doação")

    def obter_doacao(self, ator: Ator, doacao_id: str) -> dict:
        d = self._doacao_visivel(ator, self.banco.um("""SELECT d.*, i.nome AS instituicao, e.nome AS empresa FROM doacoes d
                                                         JOIN instituicoes i ON i.id=d.instituicao_id JOIN empresas e ON e.id=d.empresa_id
                                                         WHERE d.id=?""", (doacao_id,)))
        return {**d, "status_nome": ESTADOS_DOACAO.get(d["status"])}

    def avancar_doacao(self, ator: Ator, doacao_id: str, acao: str, dados: dict | None = None) -> dict:
        """Cadeia: proposta → aceita (instituição) → coletada (quem retirou) → destinada (instituição confirma). Cada passo com quem/quando."""
        dados = dados or {}
        with self.banco.transacao() as c:
            d = self._doacao_visivel(ator, self._uma(c, "SELECT * FROM doacoes WHERE id=?", (doacao_id,)))
            agora, quem = self.agora(), ator.usuario_id
            inst_ok = ator.papel == "instituicao"
            emp_ok = ator.pode("doacoes", "propor") and (ator.plataforma or ator.empresa_id == d["empresa_id"])
            if acao in ("aceitar", "recusar") and d["status"] == "proposta" and inst_ok:
                if acao == "aceitar":
                    c.execute("UPDATE doacoes SET status='aceita', aceita_por=?, aceita_em=? WHERE id=?", (quem, agora, doacao_id))
                else:
                    c.execute("UPDATE doacoes SET status='recusada', aceita_por=?, aceita_em=?, nota=? WHERE id=?",
                              (quem, agora, texto(dados.get("motivo"), 200), doacao_id))
                    self._devolver_doacao(c, d, ator)
                self.avisar(f"Doação {'aceita' if acao == 'aceitar' else 'recusada'} pela instituição.", empresa_id=d["empresa_id"], conn=c)
            elif acao == "coletar" and d["status"] == "aceita" and (inst_ok or emp_ok):
                resp = texto(dados.get("responsavel"), 120, True, "o nome de quem retirou")
                c.execute("UPDATE doacoes SET status='coletada', coleta_por=?, coleta_em=?, coleta_responsavel=? WHERE id=?",
                          (quem, agora, resp, doacao_id))
            elif acao == "confirmar" and d["status"] == "coletada" and inst_ok:
                pessoas = inteiro(dados.get("pessoas_beneficiadas"), "o número de pessoas beneficiadas", 1, 100000)
                c.execute("UPDATE doacoes SET status='destinada', destinada_por=?, destinada_em=?, pessoas_beneficiadas=? WHERE id=?",
                          (quem, agora, pessoas, doacao_id))
                if d["pedido_id"]:
                    p = self._uma(c, "SELECT * FROM pedidos WHERE id=?", (d["pedido_id"],))
                    self._mudar(c, p, "destinado", ator, "doação confirmada pela instituição")
                self.avisar("Doação confirmada pela instituição. Impacto registrado.", empresa_id=d["empresa_id"], conn=c)
            elif acao == "cancelar" and d["status"] in ("proposta", "aceita") and emp_ok:
                c.execute("UPDATE doacoes SET status='cancelada', nota=? WHERE id=?", (texto(dados.get("motivo"), 200), doacao_id))
                self._devolver_doacao(c, d, ator)
            else:
                raise ErroNegocio("Ação não permitida neste momento da doação ou para o seu perfil.")
        self.auditar(ator, f"doacao.{acao}", doacao_id, empresa_id=d["empresa_id"])
        return self.obter_doacao(ator, doacao_id)

    def _devolver_doacao(self, c, d, ator):
        if not d["oferta_id"]:
            return
        o = self._uma(c, "SELECT * FROM ofertas WHERE id=?", (d["oferta_id"],))
        campo = "expirada" if o["status"] == "encerrada" else None
        if campo:
            c.execute("UPDATE ofertas SET destinada=destinada-?, expirada=expirada+? WHERE id=?", (d["quantidade"], d["quantidade"], o["id"]))
        else:
            c.execute("UPDATE ofertas SET destinada=destinada-? WHERE id=?", (d["quantidade"], o["id"]))
            self._atualizar_esgotada(c, o["id"])
        self._movimento(c, o["id"], o["empresa_id"], "ajuste", d["quantidade"], ator, motivo="doação recusada/cancelada — voltou")

    def listar_doacoes(self, ator: Ator, empresa_id: str | None = None) -> list[dict]:
        base = """SELECT d.*, i.nome AS instituicao, e.nome AS empresa FROM doacoes d JOIN instituicoes i ON i.id=d.instituicao_id
                  JOIN empresas e ON e.id=d.empresa_id"""
        if ator.papel == "instituicao":
            linhas = self.banco.todos(base + " WHERE d.instituicao_id=? ORDER BY d.proposta_em DESC", (ator.instituicao_id,))
        else:
            ator.exigir("doacoes", "ver")
            if ator.plataforma and not empresa_id:
                linhas = self.banco.todos(base + " ORDER BY d.proposta_em DESC")
            else:
                linhas = self.banco.todos(base + " WHERE d.empresa_id=? ORDER BY d.proposta_em DESC", (ator.empresa_alvo(empresa_id),))
        return [{**d, "status_nome": ESTADOS_DOACAO.get(d["status"])} for d in linhas]

    # ================================================================ IMPACTO
    def impacto(self, ator: Ator | None = None, empresa_id: str | None = None, cliente_id: str | None = None) -> dict:
        """Só conta o que foi CONFIRMADO: pedido concluído (retirado/entregue) e doação destinada."""
        cond_p, cond_d, par = "", "", ()
        if cliente_id:
            cond_p, par = " AND p.cliente_id=?", (cliente_id,)
        elif ator is not None and ator.papel == "instituicao":
            cond_p, cond_d = " AND 0", " AND d.instituicao_id=?"
        elif ator is not None:
            ator.exigir("impacto", "ver")
            if not (ator.plataforma and not empresa_id):
                eid = ator.empresa_alvo(empresa_id)
                cond_p, cond_d, par = " AND p.empresa_id=?", " AND d.empresa_id=?", (eid,)
        v = self.banco.um(f"""SELECT COUNT(*) AS pedidos, COALESCE(SUM(peso_kg),0) AS kg, COALESCE(SUM(normal_centavos-subtotal_centavos),0) AS economia,
                                     COALESCE(SUM(repasse_centavos),0) AS receita,
                                     COALESCE((SELECT SUM(i.quantidade) FROM pedido_itens i JOIN pedidos p ON p.id=i.pedido_id WHERE p.status='concluido' {cond_p}),0) AS unidades
                              FROM pedidos p WHERE p.status='concluido' {cond_p}""", par + par)
        par_d = (ator.instituicao_id,) if (ator is not None and ator.papel == "instituicao" and not cliente_id) else (par if cond_d else ())
        if cliente_id:
            d = {"kg": 0, "unidades": 0, "doacoes": 0, "instituicoes": 0, "pessoas": 0}
        else:
            d = self.banco.um(f"""SELECT COALESCE(SUM(peso_kg),0) AS kg, COALESCE(SUM(quantidade),0) AS unidades, COUNT(*) AS doacoes,
                                         COUNT(DISTINCT instituicao_id) AS instituicoes, COALESCE(SUM(pessoas_beneficiadas),0) AS pessoas
                                  FROM doacoes d WHERE d.status='destinada' {cond_d}""", par_d)
        ofertas = 0
        if not cliente_id and not (ator is not None and ator.papel == "instituicao"):
            ofertas = self.banco.um(f"SELECT COUNT(*) AS n FROM ofertas p WHERE (vendida>0 OR destinada>0) {cond_p}", par)["n"]
        return {"pedidos": v["pedidos"], "kg_vendidos": round(v["kg"], 2), "unidades_vendidas": v["unidades"],
                "economia_clientes_centavos": v["economia"], "receita_parceiros_centavos": v["receita"],
                "kg_doados": round(d["kg"], 2), "unidades_doadas": d["unidades"], "doacoes": d["doacoes"],
                "instituicoes_atendidas": d["instituicoes"], "pessoas_beneficiadas": d["pessoas"],
                "ofertas_recuperadas": ofertas, "kg_desperdicio_evitado": round(v["kg"] + d["kg"], 2)}


class FinanceiroDetalhadoMixin:
    """Financeiro completo por período: Desenvolvedor (todas as empresas, receita da plataforma) e empresa (o próprio negócio)."""

    def financeiro_detalhado(self, ator: Ator, empresa_id: str | None = None, de=None, ate=None, incluir_teste=None) -> dict:
        ator.exigir("financeiro", "ver")
        from datetime import timedelta as _td
        from .nucleo import iso as _iso, ler_data as _ld
        hoje = self.agora_dt()
        fim_dt = (_ld(ate) + _td(days=1)) if ate else hoje + _td(seconds=1)
        ini_dt = _ld(de) if de else (hoje - _td(days=29)).replace(hour=0, minute=0, second=0)
        i, f = _iso(ini_dt), _iso(fim_dt)
        plataforma = ator.plataforma and not empresa_id
        cond, par = ("", ()) if plataforma else (" AND p.empresa_id=?", (ator.empresa_alvo(empresa_id),))
        reais = self.banco.um("SELECT COUNT(*) AS n FROM empresas WHERE demonstracao=0")["n"]
        if incluir_teste in (None, ""):
            incluir_teste = reais == 0
        else:
            incluir_teste = str(incluir_teste) in ("1", "true", "True")
        if plataforma and not incluir_teste:
            cond += " AND p.empresa_id IN (SELECT id FROM empresas WHERE demonstracao=0)"
        fat = ",".join("?" * len(ESTADOS_FATURADOS))
        base = f"FROM pedidos p WHERE p.criado_em>=? AND p.criado_em<? {cond}"
        b = self.banco
        tot = b.um(f"""SELECT COUNT(*) AS pedidos, COALESCE(SUM(total_centavos),0) AS gmv, COALESCE(SUM(subtotal_centavos),0) AS produtos,
                              COALESCE(SUM(normal_centavos-subtotal_centavos),0) AS economia, COALESCE(SUM(taxa_centavos),0) AS taxa,
                              COALESCE(SUM(repasse_centavos),0) AS repasse, COALESCE(SUM(entrega_centavos),0) AS entrega,
                              COALESCE(SUM(CASE WHEN modo='entrega' THEN 1 ELSE 0 END),0) AS entregas,
                              COALESCE(SUM(CASE WHEN modo='retirada' THEN 1 ELSE 0 END),0) AS retiradas,
                              COALESCE(SUM(CASE WHEN repasse_id IS NULL THEN repasse_centavos ELSE 0 END),0) AS a_repassar,
                              COALESCE(SUM(peso_kg),0) AS kg
                       {base} AND p.status IN ({fat})""", (i, f, *par, *ESTADOS_FATURADOS))
        por_status = {r["status"]: r for r in b.todos(f"SELECT p.status, COUNT(*) AS n, COALESCE(SUM(total_centavos),0) AS v {base} GROUP BY p.status", (i, f, *par))}
        cont = lambda st: por_status.get(st, {}).get("n", 0)  # noqa: E731
        estornos = b.um(f"""SELECT COUNT(*) AS n, COALESCE(SUM(g.valor_centavos),0) AS v FROM pagamentos g JOIN pedidos p ON p.id=g.pedido_id
                            WHERE g.status IN ('estornado','estorno_pendente') AND p.criado_em>=? AND p.criado_em<? {cond}""", (i, f, *par))
        repassado = b.um(f"""SELECT COALESCE(SUM(x.valor_centavos),0) AS v FROM repasses x WHERE x.status='pago' AND x.pago_em>=? AND x.pago_em<?
                             {cond.replace('p.empresa_id', 'x.empresa_id')}""", (i, f, *par))["v"]
        fat_par = ("", ()) if plataforma else (" AND fa.empresa_id=?", par)
        mens = b.um(f"""SELECT COALESCE(SUM(CASE WHEN fa.status='paga' THEN fa.valor_centavos ELSE 0 END),0) AS pagas,
                               COALESCE(SUM(CASE WHEN fa.status='aberta' THEN fa.valor_centavos ELSE 0 END),0) AS abertas
                        FROM faturas fa WHERE fa.criada_em>=? AND fa.criada_em<? {fat_par[0]}""", (i, f, *fat_par[1]))
        por_dia = b.todos(f"""SELECT substr(p.criado_em,1,10) AS dia, COUNT(*) AS pedidos, SUM(p.subtotal_centavos) AS vendas,
                                     SUM(p.taxa_centavos) AS taxa, SUM(p.repasse_centavos) AS repasse, SUM(p.entrega_centavos) AS entrega
                              {base} AND p.status IN ({fat}) GROUP BY dia ORDER BY dia""", (i, f, *par, *ESTADOS_FATURADOS))
        produtos = b.todos(f"""SELECT it.nome, SUM(it.quantidade) AS unidades, SUM(it.preco_centavos*it.quantidade) AS vendas
                               FROM pedido_itens it JOIN pedidos p ON p.id=it.pedido_id
                               WHERE p.criado_em>=? AND p.criado_em<? {cond} AND p.status IN ({fat})
                               GROUP BY it.nome ORDER BY vendas DESC LIMIT 10""", (i, f, *par, *ESTADOS_FATURADOS))
        empresas = []
        if plataforma:
            empresas = b.todos(f"""SELECT e.id, e.nome, e.demonstracao, pl.nome AS plano, c.pix_tipo, c.pix_chave, c.titular, c.banco,
                                          COUNT(p.id) AS pedidos, COALESCE(SUM(p.subtotal_centavos),0) AS vendas, COALESCE(SUM(p.taxa_centavos),0) AS taxa,
                                          COALESCE(SUM(p.repasse_centavos),0) AS repasse,
                                          COALESCE(SUM(CASE WHEN p.repasse_id IS NULL THEN p.repasse_centavos ELSE 0 END),0) AS a_repassar,
                                          (SELECT COALESCE(SUM(fa.valor_centavos),0) FROM faturas fa WHERE fa.empresa_id=e.id AND fa.status='aberta') AS mensalidade_aberta
                                   FROM empresas e LEFT JOIN planos pl ON pl.id=e.plano_id LEFT JOIN config_empresa c ON c.empresa_id=e.id
                                   LEFT JOIN pedidos p ON p.empresa_id=e.id AND p.criado_em>=? AND p.criado_em<? AND p.status IN ({fat})
                                   WHERE (? OR e.demonstracao=0) GROUP BY e.id ORDER BY vendas DESC""",
                               (i, f, *ESTADOS_FATURADOS, 1 if incluir_teste else 0))
        pedidos_validos = tot["pedidos"] or 0
        receita_plataforma = tot["taxa"] + mens["pagas"]
        r = {
            "periodo": {"de": i, "ate": f}, "visao": "plataforma" if plataforma else "empresa", "incluindo_teste": bool(incluir_teste),
            "pedidos": pedidos_validos, "ticket_medio_centavos": round(tot["gmv"] / pedidos_validos) if pedidos_validos else 0,
            "gmv_centavos": tot["gmv"], "vendas_produtos_centavos": tot["produtos"], "economia_clientes_centavos": tot["economia"],
            "taxa_centavos": tot["taxa"], "repasse_centavos": tot["repasse"], "a_repassar_centavos": tot["a_repassar"],
            "repassado_no_periodo_centavos": repassado, "entrega_centavos": tot["entrega"], "entregas": tot["entregas"], "retiradas": tot["retiradas"],
            "kg": round(tot["kg"], 2), "cancelados": cont("cancelado"), "nao_retirados": cont("nao_retirado"), "expirados": cont("expirado"),
            "em_andamento": sum(v["n"] for k, v in por_status.items() if k not in ESTADOS_FATURADOS + ("cancelado", "expirado", "criado", "aguardando_pagamento")),
            "estornos": estornos, "mensalidades_pagas_centavos": mens["pagas"], "mensalidades_abertas_centavos": mens["abertas"],
            "receita_plataforma_centavos": receita_plataforma, "por_dia": por_dia, "produtos": produtos, "empresas": empresas,
            "aviso": None if self._mp() else "Pagamentos em MODO TESTE: nenhum dinheiro real foi movimentado.",
        }
        if not plataforma:
            e = b.um("SELECT * FROM empresas WHERE id=?", (par[0],))
            cfg = b.um("SELECT pix_tipo, pix_chave, titular, banco FROM config_empresa WHERE empresa_id=?", (par[0],)) or {}
            pl = self.plano_da_empresa(e)
            r["empresa"] = {"nome": e["nome"], "taxa_percentual": self.taxa_da_empresa(e), "plano": pl["nome"] if pl else None,
                            "mensalidade_centavos": pl["mensalidade_centavos"] if pl else 0, "dados_repasse": cfg,
                            "receita_liquida_centavos": tot["repasse"]}
        return r
