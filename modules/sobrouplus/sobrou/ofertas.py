"""Ofertas antissobra (produto, cesta surpresa, kit), fotos, estoque e preço inteligente."""
from __future__ import annotations

import base64
import json

from .nucleo import (Ator, ErroNegocio, NaoEncontrado, SemPermissao, centavos, distancia_km, inteiro, jcarregar,
                     ler_data, normalizar_data, novo_id, real, texto)

TIPOS_OFERTA = {"produto": "Produto específico", "cesta": "Cesta surpresa", "kit": "Kit de excedentes"}
CATEGORIAS = ("refeicoes", "pizza", "padaria", "frutas", "verduras", "mercado", "sushi", "doces", "bebidas", "cafe",
              "cesta_surpresa", "outros")
STATUS_OFERTA = ("rascunho", "ativa", "pausada", "esgotada", "encerrada")
REGRAS_PRECO = ("fixo", "progressivo", "estoque")
TAMANHO_MAX_FOTO = 2_500_000
ASSINATURAS = {b"\xff\xd8\xff": ("jpg", "image/jpeg"), b"\x89PNG": ("png", "image/png"), b"RIFF": ("webp", "image/webp")}


def disponivel(o: dict) -> int:
    return max(0, o["quantidade_total"] - o["reservada"] - o["vendida"] - o["expirada"] - o["destinada"])


def _ler_imagem(dados_b64: str) -> tuple[bytes, str, str]:
    if not dados_b64:
        raise ErroNegocio("Envie a foto.")
    if "," in dados_b64[:100]:
        dados_b64 = dados_b64.split(",", 1)[1]
    try:
        bruto = base64.b64decode(dados_b64, validate=False)
    except ValueError as e:
        raise ErroNegocio("Foto inválida.") from e
    if len(bruto) > TAMANHO_MAX_FOTO:
        raise ErroNegocio("Foto grande demais (máximo 2,5 MB depois de comprimida).")
    for assinatura, (ext, tipo) in ASSINATURAS.items():
        if bruto.startswith(assinatura) and (ext != "webp" or bruto[8:12] == b"WEBP"):
            return bruto, ext, tipo
    raise ErroNegocio("Formato de foto não aceito. Use JPG, PNG ou WebP.")


_ALIASES = {"preco": "preco_base_centavos", "preco_centavos": "preco_base_centavos", "preco_normal": "preco_normal_centavos",
            "preco_minimo": "preco_minimo_centavos", "valor_estimado_min": "valor_estimado_min_centavos",
            "valor_estimado_max": "valor_estimado_max_centavos"}


def _aliases(dados: dict) -> dict:
    d = dict(dados)
    for apelido, nome in _ALIASES.items():
        if apelido in d:
            v = d.pop(apelido)
            d.setdefault(nome, v)
    return d


class OfertasMixin:
    # ================================================================ FOTOS
    def enviar_foto(self, ator: Ator, dados: dict) -> dict:
        """Recebe a foto já comprimida no navegador (principal até 1280 px + miniatura 400 px)."""
        ator.exigir("ofertas", "editar")
        eid = ator.empresa_alvo(dados.get("empresa_id"))
        bruto, ext, tipo = _ler_imagem(dados.get("imagem"))
        mini = _ler_imagem(dados["miniatura"])[0] if dados.get("miniatura") else None
        fid = novo_id()
        pasta = self.pasta_fotos / eid
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"{fid}.{ext}").write_bytes(bruto)
        nome_mini = None
        if mini:
            nome_mini = f"{fid}_mini.{ext}"
            (pasta / nome_mini).write_bytes(mini)
        self.banco.executar("INSERT INTO fotos(id, empresa_id, arquivo, miniatura, tipo, bytes, criada_em) VALUES (?,?,?,?,?,?,?)",
                            (fid, eid, f"{eid}/{fid}.{ext}", f"{eid}/{nome_mini}" if nome_mini else None, tipo, len(bruto), self.agora()))
        self.auditar(ator, "foto.enviar", fid, {"bytes": len(bruto)}, empresa_id=eid)
        return {"id": fid, "url": f"fotos/{fid}", "miniatura": f"fotos/{fid}/mini"}

    def arquivo_foto(self, foto_id: str, mini: bool = False):
        f = self.banco.um("SELECT * FROM fotos WHERE id=?", (foto_id,))
        if not f:
            raise NaoEncontrado("Foto não encontrada.")
        nome = f["miniatura"] if mini and f["miniatura"] else f["arquivo"]
        caminho = (self.pasta_fotos / nome).resolve()
        if self.pasta_fotos.resolve() not in caminho.parents or not caminho.is_file():
            raise NaoEncontrado("Foto não encontrada.")
        return caminho, f["tipo"]

    # ================================================================ OFERTAS
    def _validar_regra_preco(self, regra: str, dados_regra, minimo: int | None) -> str | None:
        if regra not in REGRAS_PRECO:
            raise ErroNegocio("Regra de preço inválida.")
        if regra == "fixo":
            return None
        degraus = dados_regra if isinstance(dados_regra, list) else jcarregar(dados_regra, [])
        limpos = []
        chave = "minutos_antes_fim" if regra == "progressivo" else "restante_ate"
        for d in degraus:
            limiar = inteiro(d.get(chave), "o gatilho do degrau", 0)
            preco = centavos(d.get("preco_centavos", d.get("preco")), "o preço do degrau")
            if minimo is not None and preco < minimo:
                raise ErroNegocio("Um degrau da regra ficou abaixo do preço mínimo que você definiu.")
            limpos.append({chave: limiar, "preco_centavos": preco})
        if not limpos:
            raise ErroNegocio("A regra de preço automático precisa de pelo menos um degrau.")
        return json.dumps(limpos)

    def salvar_oferta(self, ator: Ator, dados: dict, oferta_id: str | None = None) -> dict:
        ator.exigir("ofertas", "editar")
        atual = None
        dados = _aliases(dados)
        if oferta_id:
            atual = ator.conferir_empresa(self.banco.um("SELECT * FROM ofertas WHERE id=?", (oferta_id,)), "Oferta")
            dados = {**atual, "regra_preco_dados": jcarregar(atual["regra_preco_dados"], []), **dados}
            eid = atual["empresa_id"]
        else:
            eid = ator.empresa_alvo(dados.get("empresa_id"))
        unidade = self.banco.um("SELECT * FROM unidades WHERE id=? AND empresa_id=?", (dados.get("unidade_id"), eid))
        if not unidade:
            raise ErroNegocio("Escolha a unidade da oferta.")
        tipo = dados.get("tipo") or "produto"
        if tipo not in TIPOS_OFERTA:
            raise ErroNegocio("Tipo de oferta inválido.")
        categoria = dados.get("categoria") or ("cesta_surpresa" if tipo == "cesta" else "outros")
        if categoria not in CATEGORIAS:
            raise ErroNegocio("Categoria inválida.")
        normal = centavos(dados.get("preco_normal_centavos"), "o preço normal")
        base = centavos(dados.get("preco_base_centavos"), "o preço Sobrou+")
        if base <= 0 or base >= normal:
            raise ErroNegocio("O preço Sobrou+ precisa ser maior que zero e menor que o preço normal.")
        minimo = centavos(dados.get("preco_minimo_centavos"), "o preço mínimo", False)
        if minimo is not None and minimo > base:
            raise ErroNegocio("O preço mínimo não pode ser maior que o preço Sobrou+.")
        vmin = centavos(dados.get("valor_estimado_min_centavos"), "o valor estimado", False)
        vmax = centavos(dados.get("valor_estimado_max_centavos"), "o valor estimado", False)
        if tipo == "cesta" and (not vmin or not vmax or vmin > vmax):
            raise ErroNegocio("Na cesta surpresa, informe a faixa de valor estimado (mínimo e máximo).")
        total = inteiro(dados.get("quantidade_total"), "a quantidade", 1, 10000)
        if atual:
            usada = atual["reservada"] + atual["vendida"] + atual["expirada"] + atual["destinada"]
            if total < usada:
                raise ErroNegocio(f"A quantidade não pode ficar abaixo do que já foi reservado/vendido ({usada}).")
        inicio = normalizar_data(dados.get("inicio"), True, "o início da venda")
        fim = normalizar_data(dados.get("fim"), True, "o fim da venda")
        if fim <= inicio:
            raise ErroNegocio("O fim da venda precisa ser depois do início.")
        r_ini = normalizar_data(dados.get("retirada_inicio"))
        r_fim = normalizar_data(dados.get("retirada_fim"))
        if (r_ini and not r_fim) or (r_fim and not r_ini) or (r_ini and r_fim <= r_ini):
            raise ErroNegocio("Janela de retirada inválida (início e fim, fim depois do início).")
        validade = normalizar_data(dados.get("validade"))
        if validade and r_fim and validade < r_fim:
            raise ErroNegocio("A validade não pode terminar antes da janela de retirada.")
        retirada = 1 if dados.get("permite_retirada", 1) in (1, True, "1", "on", "true") else 0
        entrega = 1 if dados.get("permite_entrega") in (1, True, "1", "on", "true") else 0
        if not retirada and not entrega:
            raise ErroNegocio("Escolha retirada, entrega ou as duas.")
        if retirada and not r_ini:
            raise ErroNegocio("Informe a janela de retirada.")
        regra = dados.get("regra_preco") or "fixo"
        regra_dados = self._validar_regra_preco(regra, dados.get("regra_preco_dados"), minimo)
        foto_id = dados.get("foto_id") or None
        if foto_id and not self.banco.um("SELECT id FROM fotos WHERE id=? AND empresa_id=?", (foto_id, eid)):
            raise ErroNegocio("Foto inválida.")
        campos = {
            "unidade_id": unidade["id"], "tipo": tipo, "nome": texto(dados.get("nome"), 120, True, "o nome da oferta"),
            "descricao": texto(dados.get("descricao"), 1000), "categoria": categoria, "foto_id": foto_id,
            "preco_normal_centavos": normal, "preco_base_centavos": base, "preco_minimo_centavos": minimo,
            "valor_estimado_min_centavos": vmin, "valor_estimado_max_centavos": vmax, "quantidade_total": total,
            "limite_por_cliente": inteiro(dados.get("limite_por_cliente"), "o limite por cliente", 1, 100, 5),
            "estoque_critico": inteiro(dados.get("estoque_critico"), "o estoque crítico", 0, 1000, 2),
            "peso_kg_unidade": real(dados.get("peso_kg_unidade"), "o peso", 0.01, 100) or 0.5,
            "inicio": inicio, "fim": fim, "retirada_inicio": r_ini, "retirada_fim": r_fim,
            "permite_retirada": retirada, "permite_entrega": entrega, "validade": validade,
            "prioridade": inteiro(dados.get("prioridade"), "a prioridade", 0, 10, 0),
            "regra_preco": regra, "regra_preco_dados": regra_dados, "atualizada_em": self.agora(),
        }
        if atual:
            sets = ", ".join(f"{k}=?" for k in campos)
            self.banco.executar(f"UPDATE ofertas SET {sets} WHERE id=?", (*campos.values(), oferta_id))
            if total != atual["quantidade_total"]:
                self._movimento(None, oferta_id, eid, "ajuste", total - atual["quantidade_total"], ator, motivo="quantidade editada")
            if base != atual["preco_base_centavos"]:
                self._registrar_preco(None, atual, atual["preco_centavos"], base, "manual", ator, "preço editado")
                self.banco.executar("UPDATE ofertas SET preco_centavos=? WHERE id=?", (base, oferta_id))
            self.auditar(ator, "oferta.editar", oferta_id, {"campos": sorted(k for k in dados if k in campos)}, empresa_id=eid)
        else:
            oferta_id = novo_id()
            campos |= {"id": oferta_id, "empresa_id": eid, "preco_centavos": base, "status": "rascunho",
                       "criada_por": ator.usuario_id, "criada_em": self.agora()}
            self.banco.executar(f"INSERT INTO ofertas({', '.join(campos)}) VALUES ({', '.join('?' * len(campos))})", tuple(campos.values()))
            self._movimento(None, oferta_id, eid, "entrada", total, ator, motivo="oferta criada")
            self.auditar(ator, "oferta.criar", oferta_id, {"nome": campos["nome"], "quantidade": total, "preco": base}, empresa_id=eid)
        if dados.get("fotos") is not None:
            self.banco.executar("DELETE FROM oferta_fotos WHERE oferta_id=?", (oferta_id,))
            for i, fid in enumerate(dados.get("fotos") or []):
                if self.banco.um("SELECT id FROM fotos WHERE id=? AND empresa_id=?", (fid, eid)):
                    self.banco.executar("INSERT OR IGNORE INTO oferta_fotos(oferta_id, foto_id, ordem) VALUES (?,?,?)", (oferta_id, fid, i))
        self.aplicar_preco(oferta_id)
        return self.obter_oferta(ator, oferta_id)

    def mudar_status_oferta(self, ator: Ator, oferta_id: str, status: str) -> dict:
        ator.exigir("ofertas", "editar")
        o = ator.conferir_empresa(self.banco.um("SELECT * FROM ofertas WHERE id=?", (oferta_id,)), "Oferta")
        if status not in ("ativa", "pausada", "encerrada"):
            raise ErroNegocio("Status inválido.")
        if o["status"] == "encerrada":
            raise ErroNegocio("Oferta encerrada não pode ser reaberta. Crie uma nova.")
        if status == "ativa":
            emp = self.banco.um("SELECT aprovada, ativa FROM empresas WHERE id=?", (o["empresa_id"],))
            if not emp["aprovada"]:
                raise ErroNegocio("Sua empresa ainda está em análise pela equipe Sobrou+. Assim que aprovar, você poderá publicar.")
            if o["fim"] <= self.agora():
                raise ErroNegocio("O horário de venda desta oferta já terminou. Ajuste o fim da venda.")
            if not o["foto_id"]:
                raise ErroNegocio("Coloque uma foto real do alimento antes de publicar.")
            if disponivel(o) <= 0:
                status = "esgotada"
            pl = self.plano_da_empresa(self.banco.um("SELECT * FROM empresas WHERE id=?", (o["empresa_id"],)))
            if pl and pl["limite_ofertas"] and o["status"] not in ("ativa", "esgotada"):
                no_ar = self.banco.um("SELECT COUNT(*) AS n FROM ofertas WHERE empresa_id=? AND status IN ('ativa','esgotada')", (o["empresa_id"],))["n"]
                if no_ar >= pl["limite_ofertas"]:
                    raise ErroNegocio(f"O plano {pl['nome']} permite {pl['limite_ofertas']} ofertas no ar ao mesmo tempo. Encerre uma ou mude de plano.")
        with self.banco.transacao() as c:
            c.execute("UPDATE ofertas SET status=?, atualizada_em=? WHERE id=?", (status, self.agora(), oferta_id))
            if status == "encerrada":
                self._encerrar_oferta(c, {**o, "status": status}, ator, "encerrada pelo parceiro")
        self.auditar(ator, "oferta.status", oferta_id, {"de": o["status"], "para": status}, empresa_id=o["empresa_id"])
        return self.obter_oferta(ator, oferta_id)

    def ajustar_estoque(self, ator: Ator, oferta_id: str, delta: int, motivo: str) -> dict:
        """Entrada/saída manual (ex.: sobrou mais, ou quebrou/estragou). Nunca abaixo do já comprometido."""
        ator.exigir("estoque", "editar")
        motivo = texto(motivo, 200, True, "o motivo")
        delta = inteiro(delta, "o ajuste", -10000, 10000)
        with self.banco.transacao() as c:
            o = ator.conferir_empresa(self._uma(c, "SELECT * FROM ofertas WHERE id=?", (oferta_id,)), "Oferta")
            if delta < 0 and -delta > disponivel(o):
                raise ErroNegocio(f"Só há {disponivel(o)} disponíveis para retirar do estoque.")
            c.execute("UPDATE ofertas SET quantidade_total=quantidade_total+?, atualizada_em=? WHERE id=?", (delta, self.agora(), oferta_id))
            self._movimento(c, oferta_id, o["empresa_id"], "ajuste", delta, ator, motivo=motivo)
            self._atualizar_esgotada(c, oferta_id)
        self.auditar(ator, "estoque.ajuste", oferta_id, {"delta": delta, "motivo": motivo}, empresa_id=o["empresa_id"])
        self.aplicar_preco(oferta_id)
        return self.obter_oferta(ator, oferta_id)

    def alterar_preco(self, ator: Ator, oferta_id: str, novo_preco) -> dict:
        ator.exigir("preco", "editar")
        o = ator.conferir_empresa(self.banco.um("SELECT * FROM ofertas WHERE id=?", (oferta_id,)), "Oferta")
        novo = centavos(novo_preco, "o novo preço")
        if novo <= 0 or novo >= o["preco_normal_centavos"]:
            raise ErroNegocio("O preço Sobrou+ precisa ser maior que zero e menor que o preço normal.")
        if o["preco_minimo_centavos"] is not None and novo < o["preco_minimo_centavos"]:
            raise ErroNegocio("Abaixo do preço mínimo definido para esta oferta.")
        with self.banco.transacao() as c:
            c.execute("UPDATE ofertas SET preco_base_centavos=?, preco_centavos=?, atualizada_em=? WHERE id=?", (novo, novo, self.agora(), oferta_id))
            self._registrar_preco(c, o, o["preco_centavos"], novo, "manual", ator, "alteração manual")
        self.auditar(ator, "preco.manual", oferta_id, {"de": o["preco_centavos"], "para": novo}, empresa_id=o["empresa_id"])
        self.aplicar_preco(oferta_id)
        return self.obter_oferta(ator, oferta_id)

    # ---------------------------------------------------------------- consultas
    def _enriquecer(self, o: dict, lat=None, lng=None) -> dict:
        d = disponivel(o)
        normal, preco = o["preco_normal_centavos"], o["preco_centavos"]
        fotos = [f["foto_id"] for f in self.banco.todos("SELECT foto_id FROM oferta_fotos WHERE oferta_id=? ORDER BY ordem", (o["id"],))]
        if o.get("foto_id") and o["foto_id"] not in fotos:
            fotos.insert(0, o["foto_id"])
        return {**o, "disponivel": d, "restante": d,
                "desconto_pct": round(100 * (normal - preco) / normal) if normal else 0,
                "estoque_baixo": 0 < d <= o["estoque_critico"],
                "tipo_nome": TIPOS_OFERTA.get(o["tipo"]), "fotos": [f"fotos/{f}" for f in fotos],
                "foto": f"fotos/{fotos[0]}" if fotos else None, "miniatura": f"fotos/{fotos[0]}/mini" if fotos else None,
                "regra_preco_dados": jcarregar(o.get("regra_preco_dados"), []),
                "distancia_km": distancia_km(lat, lng, o.get("lat"), o.get("lng")) if lat is not None else None}

    def obter_oferta(self, ator: Ator, oferta_id: str) -> dict:
        ator.exigir("ofertas", "ver")
        o = ator.conferir_empresa(self.banco.um("""SELECT o.*, u.nome AS unidade, u.lat, u.lng, e.nome AS empresa
                                                    FROM ofertas o JOIN unidades u ON u.id=o.unidade_id JOIN empresas e ON e.id=o.empresa_id
                                                    WHERE o.id=?""", (oferta_id,)), "Oferta")
        r = self._enriquecer(o)
        r["historico_precos"] = self.banco.todos("SELECT * FROM historico_precos WHERE oferta_id=? ORDER BY quando DESC LIMIT 30", (oferta_id,))
        r["movimentos"] = self.banco.todos("""SELECT m.*, u.nome AS usuario FROM movimentos_estoque m LEFT JOIN usuarios u ON u.id=m.usuario_id
                                              WHERE m.oferta_id=? ORDER BY m.quando DESC LIMIT 50""", (oferta_id,))
        return r

    def listar_ofertas(self, ator: Ator, empresa_id: str | None = None, status: str | None = None) -> list[dict]:
        ator.exigir("ofertas", "ver")
        cond, p = [], []
        if not (ator.plataforma and not empresa_id):
            cond.append("o.empresa_id=?")
            p.append(ator.empresa_alvo(empresa_id))
        if status:
            cond.append("o.status=?")
            p.append(status)
        where = ("WHERE " + " AND ".join(cond)) if cond else ""
        linhas = self.banco.todos(f"""SELECT o.*, u.nome AS unidade, u.lat, u.lng, e.nome AS empresa FROM ofertas o
                                      JOIN unidades u ON u.id=o.unidade_id JOIN empresas e ON e.id=o.empresa_id {where}
                                      ORDER BY CASE o.status WHEN 'ativa' THEN 0 WHEN 'esgotada' THEN 1 WHEN 'rascunho' THEN 2
                                      WHEN 'pausada' THEN 3 ELSE 4 END, o.fim""", tuple(p))
        return [self._enriquecer(o) for o in linhas]

    def vitrine(self, filtros: dict | None = None) -> list[dict]:
        """Marketplace público: só ofertas ativas, de empresas aprovadas e ativas, dentro do horário de venda."""
        f = filtros or {}
        agora = self.agora()
        cond = ["o.status='ativa'", "o.inicio<=?", "o.fim>?", "e.aprovada=1", "e.ativa=1", "u.ativa=1"]
        p: list = [agora, agora]
        if f.get("categoria") and f["categoria"] != "todos":
            cond.append("o.categoria=?")
            p.append(f["categoria"])
        if f.get("tipo"):
            cond.append("o.tipo=?")
            p.append(f["tipo"])
        if f.get("empresa_id"):
            cond.append("o.empresa_id=?")
            p.append(f["empresa_id"])
        if f.get("modo") == "retirada":
            cond.append("o.permite_retirada=1")
        elif f.get("modo") == "entrega":
            cond.append("o.permite_entrega=1 AND c.aceita_entrega=1")
        if f.get("busca"):
            cond.append("(o.nome LIKE ? OR o.descricao LIKE ? OR e.nome LIKE ?)")
            p += [f"%{f['busca'][:60]}%"] * 3
        if f.get("preco_max"):
            cond.append("o.preco_centavos<=?")
            p.append(centavos(f["preco_max"], "o preço máximo"))
        if f.get("ate"):
            cond.append("(o.retirada_fim IS NULL OR o.retirada_fim<=?)")
            p.append(normalizar_data(f["ate"]))
        linhas = self.banco.todos(f"""SELECT o.*, u.nome AS unidade, u.endereco, u.bairro, u.cidade, u.lat, u.lng,
                                             u.instrucoes_retirada, e.nome AS empresa, e.slug, e.tipo AS empresa_tipo,
                                             c.aceita_entrega, c.taxa_entrega_centavos, c.raio_entrega_km,
                                             (SELECT pl.destaque FROM planos pl WHERE pl.id=e.plano_id) AS loja_destaque
                                      FROM ofertas o JOIN unidades u ON u.id=o.unidade_id JOIN empresas e ON e.id=o.empresa_id
                                      LEFT JOIN config_empresa c ON c.empresa_id=o.empresa_id
                                      WHERE {' AND '.join(cond)}""", tuple(p))
        lat, lng = real(f.get("lat"), "a latitude", -90, 90), real(f.get("lng"), "a longitude", -180, 180)
        notas = self.notas_empresas()
        itens = []
        for o in linhas:
            r = self._enriquecer(o, lat, lng)
            if r["disponivel"] <= 0:
                continue
            if f.get("desconto_min") and r["desconto_pct"] < int(f["desconto_min"]):
                continue
            if f.get("raio_km") and r["distancia_km"] is not None and r["distancia_km"] > float(f["raio_km"]):
                continue
            for k in ("criada_por", "regra_preco_dados", "preco_minimo_centavos", "preco_base_centavos", "reservada"):
                r.pop(k, None)
            r["nota"] = notas.get(o["empresa_id"])
            r["loja_destaque"] = bool(o.get("loja_destaque"))
            itens.append(r)
        ordem = f.get("ordem") or ("distancia" if lat is not None else "urgencia")
        if ordem == "distancia":
            itens.sort(key=lambda r: (r["distancia_km"] is None, r["distancia_km"] or 0))
        elif ordem == "desconto":
            itens.sort(key=lambda r: -r["desconto_pct"])
        elif ordem == "preco":
            itens.sort(key=lambda r: r["preco_centavos"])
        else:
            itens.sort(key=lambda r: (not r["loja_destaque"], -r["prioridade"], r["retirada_fim"] or r["fim"]))
        return itens

    def oferta_publica(self, oferta_id: str) -> dict:
        for o in self.vitrine({}):
            if o["id"] == oferta_id:
                return o
        raise NaoEncontrado("Esta oferta não está mais disponível.")

    # ================================================================ ESTOQUE E PREÇO (internos)
    @staticmethod
    def _uma(c, sql, p=()):
        r = c.execute(sql, p).fetchone()
        return dict(r) if r else None

    def _movimento(self, c, oferta_id, empresa_id, tipo, quantidade, ator: Ator | None, pedido_id=None, motivo=None):
        sql = "INSERT INTO movimentos_estoque(id, oferta_id, empresa_id, tipo, quantidade, pedido_id, usuario_id, motivo, quando) VALUES (?,?,?,?,?,?,?,?,?)"
        p = (novo_id(), oferta_id, empresa_id, tipo, quantidade, pedido_id, ator.usuario_id if ator else None, motivo, self.agora())
        (c.execute if c is not None else self.banco.executar)(sql, p)

    def _registrar_preco(self, c, oferta, de, para, origem, ator: Ator | None, motivo):
        if de == para:
            return
        sql = "INSERT INTO historico_precos(id, oferta_id, empresa_id, de_centavos, para_centavos, origem, motivo, usuario_id, quando) VALUES (?,?,?,?,?,?,?,?,?)"
        p = (novo_id(), oferta["id"], oferta["empresa_id"], de, para, origem, motivo, ator.usuario_id if ator else None, self.agora())
        (c.execute if c is not None else self.banco.executar)(sql, p)

    def _atualizar_esgotada(self, c, oferta_id):
        o = self._uma(c, "SELECT * FROM ofertas WHERE id=?", (oferta_id,))
        if o["status"] == "ativa" and disponivel(o) <= 0:
            c.execute("UPDATE ofertas SET status='esgotada' WHERE id=?", (oferta_id,))
        elif o["status"] == "esgotada" and disponivel(o) > 0 and o["fim"] > self.agora():
            c.execute("UPDATE ofertas SET status='ativa' WHERE id=?", (oferta_id,))

    def _encerrar_oferta(self, c, o, ator, motivo):
        """Fim da venda: o que não foi vendido nem reservado passa para 'expirado' (pode virar doação)."""
        sobra = disponivel(o)
        c.execute("UPDATE ofertas SET status='encerrada', expirada=expirada+?, atualizada_em=? WHERE id=?", (sobra, self.agora(), o["id"]))
        if sobra:
            self._movimento(c, o["id"], o["empresa_id"], "expiracao", sobra, ator, motivo=motivo)
            self.avisar(f"Oferta encerrada com sobra: {o['nome']} — {sobra} un. Você pode destinar para doação.",
                        empresa_id=o["empresa_id"], conn=c)

    def preco_pela_regra(self, o: dict) -> int:
        """Preço vigente = menor degrau que se aplica agora (nunca abaixo do mínimo do parceiro, nunca acima do preço base)."""
        base = o["preco_base_centavos"] if o.get("preco_base_centavos") is not None else o["preco_centavos"]
        preco = base
        degraus = jcarregar(o.get("regra_preco_dados"), [])
        if o["regra_preco"] == "progressivo":
            fim = ler_data(o["fim"])
            faltam = (fim - self.agora_dt()).total_seconds() / 60
            for d in degraus:
                if faltam <= d["minutos_antes_fim"]:
                    preco = min(preco, d["preco_centavos"])
        elif o["regra_preco"] == "estoque":
            restante = disponivel(o)
            for d in degraus:
                if restante <= d["restante_ate"]:
                    preco = min(preco, d["preco_centavos"])
        if o.get("preco_minimo_centavos") is not None:
            preco = max(preco, o["preco_minimo_centavos"])
        return preco

    def aplicar_preco(self, oferta_id: str) -> int | None:
        o = self.banco.um("SELECT * FROM ofertas WHERE id=?", (oferta_id,))
        if not o or o["regra_preco"] == "fixo" or o["status"] in ("encerrada",):
            return None
        novo = self.preco_pela_regra(o)
        if novo != o["preco_centavos"]:
            with self.banco.transacao() as c:
                c.execute("UPDATE ofertas SET preco_centavos=?, atualizada_em=? WHERE id=?", (novo, self.agora(), oferta_id))
                self._registrar_preco(c, o, o["preco_centavos"], novo, "regra", None, f"regra {o['regra_preco']}")
            self.auditar(None, "preco.regra", oferta_id, {"de": o["preco_centavos"], "para": novo}, empresa_id=o["empresa_id"])
        return novo
