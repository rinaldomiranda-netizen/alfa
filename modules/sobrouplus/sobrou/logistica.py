"""Entregadores, Dispatch (escolha do entregador) e posição GPS enviada pelo celular do entregador.

Critérios do Dispatch (combinado §17): distância até a loja, disponibilidade (online), capacidade,
tipo do entregador (próprio da loja ou rede Sobrou+), janela do pedido / risco de expiração e prioridade.
Oferta da corrida com prazo para aceitar; recusa ou prazo vencido → próximo entregador (fallback).
"""
from __future__ import annotations

import json
from datetime import timedelta

from .nucleo import Ator, ErroNegocio, NaoEncontrado, SemPermissao, distancia_km, iso, ler_data, novo_id, real

SEGUNDOS_PARA_ACEITAR = 90
VELOCIDADE_KMH = 20      # moto/bike em cidade (estimativa de ETA)
MINUTOS_COLETA = 5
POSICAO_VALIDA_MIN = 10  # posição mais velha que isso: entregador não entra no Dispatch


class LogisticaMixin:
    # ================================================================ ENTREGADOR (app)
    def _entregador_do_ator(self, ator: Ator, c=None) -> dict:
        if ator.papel != "entregador":
            raise SemPermissao("Área só para entregadores.")
        consulta = (lambda s, p: self._uma(c, s, p)) if c is not None else self.banco.um
        e = consulta("SELECT * FROM entregadores WHERE usuario_id=?", (ator.usuario_id,))
        if not e:
            raise NaoEncontrado("Cadastro de entregador não encontrado.")
        return e

    def ficar_online(self, ator: Ator, online: bool) -> dict:
        e = self._entregador_do_ator(ator)
        self.banco.executar("UPDATE entregadores SET online=? WHERE id=?", (1 if online else 0, e["id"]))
        self.auditar(ator, "entregador.online" if online else "entregador.offline", e["id"], empresa_id=e["empresa_id"])
        if online:
            self.despachar()
        return self.painel_entregador(ator)

    def enviar_posicao(self, ator: Ator, lat, lng, precisao=None) -> dict:
        """Posição real do GPS do celular (navegador pede permissão). Nada é simulado."""
        e = self._entregador_do_ator(ator)
        la, ln = real(lat, "a latitude", -90, 90, True), real(lng, "a longitude", -180, 180, True)
        agora = self.agora()
        self.banco.executar("UPDATE entregadores SET lat=?, lng=?, posicao_em=? WHERE id=?", (la, ln, agora, e["id"]))
        self.banco.executar("INSERT INTO posicoes(id, entregador_id, lat, lng, precisao_m, quando) VALUES (?,?,?,?,?,?)",
                            (novo_id(), e["id"], la, ln, real(precisao, "a precisão", 0, 100000), agora))
        return {"ok": True}

    def painel_entregador(self, ator: Ator) -> dict:
        e = self._entregador_do_ator(ator)
        corridas = self.banco.todos("""SELECT en.*, p.numero, p.status AS pedido_status, p.endereco_entrega, p.entrega_lat, p.entrega_lng,
                                              p.janela_fim, u.nome AS loja, u.endereco AS loja_endereco, u.lat AS loja_lat, u.lng AS loja_lng,
                                              e.nome AS empresa, cl.nome AS cliente, cl.telefone AS cliente_telefone,
                                              (SELECT GROUP_CONCAT(i.quantidade || 'x ' || i.nome, ', ') FROM pedido_itens i WHERE i.pedido_id=p.id) AS resumo
                                       FROM entregas en JOIN pedidos p ON p.id=en.pedido_id JOIN unidades u ON u.id=p.unidade_id
                                       JOIN empresas e ON e.id=p.empresa_id JOIN usuarios cl ON cl.id=p.cliente_id
                                       WHERE en.entregador_id=? ORDER BY en.atualizada_em DESC LIMIT 50""", (e["id"],))
        ativas = [r for r in corridas if r["status"] in ("ofertada", "aceita", "em_coleta", "coletada", "em_rota")]
        hoje = self.agora()[:10]
        feitas = [r for r in corridas if r["status"] == "entregue"]
        return {"entregador": e, "ativas": ativas, "historico": feitas[:20],
                "ganhos_hoje_centavos": sum(r["ganho_centavos"] for r in feitas if (r["atualizada_em"] or "")[:10] == hoje),
                "ganhos_total_centavos": sum(r["ganho_centavos"] for r in feitas)}

    def responder_corrida(self, ator: Ator, entrega_id: str, aceitar: bool) -> dict:
        with self.banco.transacao() as c:
            er = self._entregador_do_ator(ator, c)
            en = self._uma(c, "SELECT * FROM entregas WHERE id=?", (entrega_id,))
            if not en or en["entregador_id"] != er["id"] or en["status"] != "ofertada":
                raise ErroNegocio("Esta corrida não está mais oferecida a você.")
            p = self._uma(c, "SELECT * FROM pedidos WHERE id=?", (en["pedido_id"],))
            if aceitar:
                if en["oferta_expira_em"] and en["oferta_expira_em"] < self.agora():
                    raise ErroNegocio("O prazo para aceitar passou. A corrida foi para outro entregador.")
                c.execute("UPDATE entregas SET status='aceita', atualizada_em=? WHERE id=?", (self.agora(), entrega_id))
                self._mudar(c, p, "entregador_designado", ator, f"entregador {ator.nome} aceitou")
                self.avisar(f"Pedido #{p['numero']}: entregador {ator.nome} a caminho da loja.", empresa_id=p["empresa_id"], conn=c)
            else:
                recusados = json.loads(en["recusados"] or "[]") + [er["id"]]
                c.execute("UPDATE entregas SET status='aguardando', entregador_id=NULL, recusados=?, atualizada_em=? WHERE id=?",
                          (json.dumps(recusados), self.agora(), entrega_id))
        self.auditar(ator, "entrega.aceitar" if aceitar else "entrega.recusar", entrega_id, empresa_id=p["empresa_id"])
        if not aceitar:
            self.despachar()
        return self.painel_entregador(ator)

    def avancar_corrida(self, ator: Ator, entrega_id: str, acao: str, codigo: str | None = None) -> dict:
        """cheguei_loja → coletei → (em rota) → entreguei (com o PIN do cliente)."""
        with self.banco.transacao() as c:
            er = self._entregador_do_ator(ator, c)
            en = self._uma(c, "SELECT * FROM entregas WHERE id=?", (entrega_id,))
            if not en or en["entregador_id"] != er["id"]:
                raise NaoEncontrado("Corrida não encontrada.")
            p = self._uma(c, "SELECT * FROM pedidos WHERE id=?", (en["pedido_id"],))
            if acao == "cheguei_loja" and en["status"] == "aceita":
                novo_en = "em_coleta"
                self._mudar(c, p, "em_coleta", ator, "entregador chegou na loja")
            elif acao == "coletei" and en["status"] == "em_coleta":
                novo_en = "em_rota"
                p = self._mudar(c, p, "em_rota", ator, "pedido coletado, em rota")
                for it in c.execute("SELECT * FROM pedido_itens WHERE pedido_id=?", (p["id"],)).fetchall():
                    self._movimento(c, it["oferta_id"], p["empresa_id"], "entrega", it["quantidade"], ator, p["id"])
            elif acao == "entreguei" and en["status"] == "em_rota":
                if (codigo or "").strip() != p["codigo_retirada"]:
                    raise ErroNegocio("Código do cliente não confere. Peça o código de 4 dígitos que aparece no app do cliente.")
                novo_en = "entregue"
                self._mudar(c, p, "entregue", ator, "entregue com código do cliente")
            else:
                raise ErroNegocio("Ação fora de ordem para esta corrida.")
            c.execute("UPDATE entregas SET status=?, atualizada_em=? WHERE id=?", (novo_en, self.agora(), entrega_id))
        self.auditar(ator, f"entrega.{acao}", entrega_id, empresa_id=p["empresa_id"])
        return self.painel_entregador(ator)

    # ================================================================ DISPATCH
    def _criar_entrega(self, c, p: dict):
        if self._uma(c, "SELECT id FROM entregas WHERE pedido_id=?", (p["id"],)):
            c.execute("UPDATE entregas SET status='aguardando', entregador_id=NULL, atualizada_em=? WHERE pedido_id=?", (self.agora(), p["id"]))
            return
        u = self._uma(c, "SELECT lat, lng FROM unidades WHERE id=?", (p["unidade_id"],))
        r = self.rota(u["lat"], u["lng"], p["entrega_lat"], p["entrega_lng"], so_cache=True) if p["entrega_lat"] is not None and u["lat"] is not None else None
        c.execute("""INSERT INTO entregas(id, pedido_id, empresa_id, status, distancia_km, eta_min, ganho_centavos, criada_em, atualizada_em)
                     VALUES (?,?,?,'aguardando',?,?,?,?,?)""",
                  (novo_id(), p["id"], p["empresa_id"], r["km"] if r else None, r["minutos"] + MINUTOS_COLETA if r else None,
                   p["entrega_centavos"], self.agora(), self.agora()))

    def _prioridade(self, p: dict) -> float:
        """Quanto menor, mais urgente: minutos até o fim da janela/validade (alimento com prazo curto sai primeiro)."""
        limite = p.get("janela_fim")
        if not limite:
            return 9999.0
        return max(0.0, (ler_data(limite) - self.agora_dt()).total_seconds() / 60)

    def candidatos(self, c, p: dict, recusados: list[str]) -> list[dict]:
        u = self._uma(c, "SELECT lat, lng FROM unidades WHERE id=?", (p["unidade_id"],))
        limite_pos = iso(self.agora_dt() - timedelta(minutes=POSICAO_VALIDA_MIN))
        linhas = [dict(r) for r in c.execute("""
            SELECT er.*, us.nome,
                   (SELECT COUNT(*) FROM entregas x WHERE x.entregador_id=er.id AND x.status IN ('ofertada','aceita','em_coleta','coletada','em_rota')) AS carga
            FROM entregadores er JOIN usuarios us ON us.id=er.usuario_id
            WHERE er.online=1 AND us.ativo=1 AND (er.empresa_id IS NULL OR er.empresa_id=?)""", (p["empresa_id"],)).fetchall()]
        lista = []
        for e in linhas:
            if e["id"] in recusados or e["carga"] >= e["capacidade"]:
                continue
            if not e["posicao_em"] or e["posicao_em"] < limite_pos:
                continue  # sem GPS recente não dá para calcular distância: não entra
            d = distancia_km(e["lat"], e["lng"], u["lat"], u["lng"])
            if d is None:
                continue
            # entregador próprio da loja tem preferência (custo menor); carga atual pesa um pouco
            nota = d + (0 if e["empresa_id"] else 0.8) + e["carga"] * 1.5
            lista.append({**e, "distancia_loja_km": d, "nota": round(nota, 2)})
        lista.sort(key=lambda e: e["nota"])
        for e in lista[:3]:  # os 3 melhores pela linha reta são conferidos pelas ruas
            r = self.rota(e["lat"], e["lng"], u["lat"], u["lng"], so_cache=True)
            if r and r["fonte"] == "ruas":
                e["nota"] = round(e["nota"] - e["distancia_loja_km"] + r["km"], 2)
                e["distancia_loja_km"] = r["km"]
                e["minutos_loja"] = r["minutos"]
        return sorted(lista, key=lambda e: e["nota"])

    def despachar(self) -> int:
        """Oferece cada corrida aguardando ao melhor entregador. Mais urgente primeiro. Devolve quantas foram oferecidas."""
        oferecidas = 0
        self._aquecer_rotas()
        agora = self.agora()
        with self.banco.transacao() as c:
            # prazo de aceite vencido = recusa automática
            for en in c.execute("SELECT * FROM entregas WHERE status='ofertada' AND oferta_expira_em<?", (agora,)).fetchall():
                rec = json.loads(en["recusados"] or "[]") + [en["entregador_id"]]
                c.execute("UPDATE entregas SET status='aguardando', entregador_id=NULL, recusados=?, atualizada_em=? WHERE id=?",
                          (json.dumps(rec), agora, en["id"]))
            fila = []
            for en in c.execute("SELECT * FROM entregas WHERE status='aguardando'").fetchall():
                p = self._uma(c, "SELECT * FROM pedidos WHERE id=?", (en["pedido_id"],))
                if p["status"] != "aguardando_entregador":
                    continue
                fila.append((self._prioridade(p), dict(en), p))
            fila.sort(key=lambda x: x[0])
            for prioridade, en, p in fila:
                rec = json.loads(en["recusados"] or "[]")
                cands = self.candidatos(c, p, rec)
                c.execute("UPDATE entregas SET prioridade=? WHERE id=?", (prioridade, en["id"]))
                if not cands:
                    continue
                e = cands[0]
                eta = (e.get("minutos_loja") or round(e["distancia_loja_km"] / VELOCIDADE_KMH * 60)) + (en["eta_min"] or MINUTOS_COLETA)
                c.execute("""UPDATE entregas SET status='ofertada', entregador_id=?, oferta_expira_em=?, eta_min=?, atualizada_em=? WHERE id=?""",
                          (e["id"], iso(self.agora_dt() + timedelta(seconds=SEGUNDOS_PARA_ACEITAR)), eta, agora, en["id"]))
                self.avisar(f"Nova corrida: pedido #{p['numero']} — responda em {SEGUNDOS_PARA_ACEITAR} s.", usuario_id=e["usuario_id"], conn=c)
                oferecidas += 1
        return oferecidas

    def _aquecer_rotas(self) -> None:
        """Antes do Dispatch (fora da transação): busca pelas ruas a distância dos entregadores mais perto até cada loja."""
        lojas = self.banco.todos("""SELECT DISTINCT u.lat, u.lng FROM entregas en JOIN pedidos p ON p.id=en.pedido_id
                                    JOIN unidades u ON u.id=p.unidade_id WHERE en.status IN ('aguardando','ofertada') AND u.lat IS NOT NULL""")
        if not lojas:
            return
        ents = self.banco.todos("SELECT lat, lng FROM entregadores WHERE online=1 AND lat IS NOT NULL")
        for l in lojas[:10]:
            perto = sorted(ents, key=lambda e: distancia_km(e["lat"], e["lng"], l["lat"], l["lng"]))[:3]
            for e in perto:
                self.rota(e["lat"], e["lng"], l["lat"], l["lng"])

    def painel_dispatch(self, ator: Ator, empresa_id: str | None = None) -> dict:
        ator.exigir("dispatch", "ver")
        cond, par = "", ()
        if not (ator.plataforma and not empresa_id):
            cond, par = "WHERE en.empresa_id=?", (ator.empresa_alvo(empresa_id),)
        entregas = self.banco.todos(f"""SELECT en.*, p.numero, p.status AS pedido_status, p.janela_fim, p.endereco_entrega,
                                               e.nome AS empresa, un.nome AS loja, us.nome AS entregador,
                                               un.lat AS loja_lat, un.lng AS loja_lng, p.entrega_lat, p.entrega_lng
                                        FROM entregas en JOIN pedidos p ON p.id=en.pedido_id JOIN empresas e ON e.id=en.empresa_id
                                        JOIN unidades un ON un.id=p.unidade_id
                                        LEFT JOIN entregadores er ON er.id=en.entregador_id LEFT JOIN usuarios us ON us.id=er.usuario_id
                                        {cond} ORDER BY CASE WHEN en.status IN ('entregue','falhou') THEN 1 ELSE 0 END, p.janela_fim, en.criada_em DESC
                                        LIMIT 100""", par)
        if ator.plataforma and not empresa_id:
            ents = self.banco.todos("""SELECT er.*, us.nome, us.telefone, e.nome AS empresa FROM entregadores er JOIN usuarios us ON us.id=er.usuario_id
                                       LEFT JOIN empresas e ON e.id=er.empresa_id ORDER BY er.online DESC, us.nome""")
        else:
            ents = self.banco.todos("""SELECT er.*, us.nome, us.telefone FROM entregadores er JOIN usuarios us ON us.id=er.usuario_id
                                       WHERE er.empresa_id=? ORDER BY er.online DESC, us.nome""", (ator.empresa_alvo(empresa_id),))
        sem = [x for x in entregas if x["status"] == "aguardando"]
        return {"entregas": entregas, "entregadores": ents, "sem_entregador": len(sem)}

    def designar_manual(self, ator: Ator, entrega_id: str, entregador_id: str) -> dict:
        """Logística escolhe o entregador na mão (fallback quando ninguém aceita)."""
        ator.exigir("dispatch", "operar")
        with self.banco.transacao() as c:
            en = ator.conferir_empresa(self._uma(c, "SELECT * FROM entregas WHERE id=?", (entrega_id,)), "Entrega")
            if en["status"] not in ("aguardando", "ofertada"):
                raise ErroNegocio("Esta entrega já tem entregador.")
            er = self._uma(c, "SELECT * FROM entregadores WHERE id=?", (entregador_id,))
            if not er or (er["empresa_id"] and er["empresa_id"] != en["empresa_id"]):
                raise ErroNegocio("Entregador inválido para esta loja.")
            c.execute("UPDATE entregas SET status='ofertada', entregador_id=?, oferta_expira_em=?, atualizada_em=? WHERE id=?",
                      (entregador_id, iso(self.agora_dt() + timedelta(seconds=SEGUNDOS_PARA_ACEITAR * 3)), self.agora(), entrega_id))
            self.avisar("Corrida designada para você pela logística. Aceite no app.", usuario_id=er["usuario_id"], conn=c)
        self.auditar(ator, "dispatch.manual", entrega_id, {"entregador": entregador_id}, empresa_id=en["empresa_id"])
        return self.painel_dispatch(ator, en["empresa_id"] if ator.plataforma else None)
