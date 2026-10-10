"""Serviços & preços, orçamentos e agenda."""
from __future__ import annotations

import html
import os
import urllib.parse
from datetime import date, datetime, timedelta, timezone

from .db import agora, para_datahora
from .nucleo import Ator, Conflito, ErroNegocio, NaoEncontrado, _texto, novo_id

STATUS_ORCAMENTO = ("rascunho", "enviado", "em_analise", "aprovado", "recusado", "vencido")
TRANSICOES_ORCAMENTO = {
    "rascunho": ("enviado",),
    "enviado": ("em_analise", "aprovado", "recusado", "rascunho"),
    "em_analise": ("aprovado", "recusado", "enviado"),
    "vencido": ("rascunho",),
    "aprovado": (),
    "recusado": ("rascunho",),
}
STATUS_AGENDA = ("agendado", "confirmado", "aguardando", "concluido", "cancelado")


def moeda(centavos: int | None) -> str:
    valor = (centavos or 0) / 100
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def centavos(valor) -> int:
    """Aceita 780, 780.5, '780,00', '1.250,00', 'R$ 780,00'."""
    if valor is None or valor == "":
        return 0
    if isinstance(valor, (int, float)):
        numero = float(valor)
    else:
        texto = str(valor).replace("R$", "").strip()
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        try:
            numero = float(texto)
        except ValueError:
            raise ErroNegocio(f"Valor inválido: {valor}") from None
    if numero < 0 or numero > 100_000_000:
        raise ErroNegocio("Valor fora do limite.")
    return int(round(numero * 100))


def _data(valor: str, campo: str) -> str:
    try:
        return date.fromisoformat(str(valor)[:10]).isoformat()
    except ValueError:
        raise ErroNegocio(f"Data inválida em '{campo}'.") from None


class ComercialMixin:
    # ================================================================ SERVIÇOS
    def _com_valores(self, empresa_id: str) -> bool:
        return "valores" not in self.recursos_desligados(empresa_id)

    @staticmethod
    def _rotulo_solicitacao() -> tuple[str, str]:
        """(nome, sigla) do documento: na igreja é 'Solicitação', nas empresas 'Orçamento'."""
        return ("Solicitação", "SOL") if os.getenv("RMD_EDICAO", "").strip().lower() == "church" else ("Orçamento", "ORC")

    def listar_servicos(self, ator: Ator, somente_ativos: bool = False) -> list[dict]:
        ator.exigir("servicos", "ver")
        sql = "SELECT * FROM servicos WHERE empresa_id=?" + (" AND ativo=1" if somente_ativos else "") + " ORDER BY ativo DESC, categoria, nome"
        return self.banco.todos(sql, (ator.empresa,))

    def salvar_servico(self, ator: Ator, dados: dict, servico_id: str | None = None) -> dict:
        ator.exigir("servicos", "editar" if servico_id else "criar")
        nome = _texto(dados.get("nome"), "nome do serviço", maximo=120)
        categoria = _texto(dados.get("categoria"), "categoria", False, 60)
        descricao = _texto(dados.get("descricao"), "descrição", False, 1000)
        preco = centavos(dados.get("preco")) if "preco" in dados else max(0, int(dados.get("preco_centavos") or 0))
        if not self._com_valores(ator.empresa):  # função "valores" desligada: não grava preço (o que já existia fica guardado)
            antigo = self.banco.um("SELECT preco_centavos FROM servicos WHERE id=? AND empresa_id=?", (servico_id, ator.empresa)) if servico_id else None
            preco = antigo["preco_centavos"] if antigo else 0
        sla = dados.get("sla_horas")
        sla = int(sla) if sla not in (None, "") else None
        if sla is not None and not 0 < sla <= 8760:
            raise ErroNegocio("Prazo (SLA) inválido.")
        ativo = 1 if dados.get("ativo", True) else 0
        if servico_id:
            if not self.banco.um("SELECT 1 AS x FROM servicos WHERE id=? AND empresa_id=?", (servico_id, ator.empresa)):
                raise NaoEncontrado("Serviço não encontrado.")
            self.banco.executar(
                "UPDATE servicos SET nome=?, categoria=?, descricao=?, preco_centavos=?, sla_horas=?, ativo=? WHERE id=?",
                (nome, categoria, descricao, preco, sla, ativo, servico_id),
            )
        else:
            servico_id = novo_id()
            self.banco.executar(
                "INSERT INTO servicos(id, empresa_id, nome, categoria, descricao, preco_centavos, sla_horas, ativo, criado_em) VALUES (?,?,?,?,?,?,?,?,?)",
                (servico_id, ator.empresa, nome, categoria, descricao, preco, sla, ativo, agora()),
            )
        self.auditar(ator, "servico.salvar", servico_id, {"nome": nome, "preco": preco})
        return self.banco.um("SELECT * FROM servicos WHERE id=?", (servico_id,))

    # ================================================================ ORÇAMENTOS
    def _atualizar_vencimento(self, orcamento: dict) -> dict:
        if orcamento.get("status") in ("enviado", "em_analise") and orcamento.get("validade") and orcamento["validade"] < date.today().isoformat():
            self.banco.executar("UPDATE orcamentos SET status='vencido', atualizado_em=? WHERE id=?", (agora(), orcamento["id"]))
            orcamento = {**orcamento, "status": "vencido"}
        return orcamento

    def listar_orcamentos(self, ator: Ator, status: str = "", busca: str = "") -> list[dict]:
        ator.exigir("orcamentos", "ver")
        sql = """SELECT o.*, c.nome AS contato_nome,
                   (SELECT GROUP_CONCAT(i.descricao, ' + ') FROM orcamento_itens i WHERE i.orcamento_id=o.id) AS servicos
                 FROM orcamentos o JOIN contatos c ON c.id=o.contato_id WHERE o.empresa_id=?"""
        parametros: list = [ator.empresa]
        if busca:
            sql += " AND (c.nome LIKE ? OR CAST(o.numero AS TEXT) LIKE ?)"
            parametros += [f"%{busca}%", f"%{busca}%"]
        linhas = [self._atualizar_vencimento(o) for o in self.banco.todos(sql + " ORDER BY o.numero DESC LIMIT 300", parametros)
                  if self._orcamento_no_alcance(ator, o)]
        if status:
            linhas = [o for o in linhas if o["status"] == status]
        return linhas

    def obter_orcamento(self, ator: Ator, orcamento_id: str, portal: bool = False) -> dict:
        ator.exigir("portal" if portal else "orcamentos", "ver")
        orcamento = self.banco.um(
            "SELECT o.*, c.nome AS contato_nome, c.telefone AS contato_telefone, c.whatsapp AS contato_whatsapp, c.email AS contato_email "
            "FROM orcamentos o JOIN contatos c ON c.id=o.contato_id WHERE o.id=? AND o.empresa_id=?",
            (orcamento_id, ator.empresa),
        )
        if not orcamento or (portal and (orcamento["contato_id"] != ator.contato_id or orcamento["status"] == "rascunho")) \
                or (not portal and not self._orcamento_no_alcance(ator, orcamento)):
            raise NaoEncontrado("Orçamento não encontrado.")
        orcamento = self._atualizar_vencimento(orcamento)
        orcamento["itens"] = self.banco.todos("SELECT * FROM orcamento_itens WHERE orcamento_id=? ORDER BY rowid", (orcamento_id,))
        orcamento["subtotal_centavos"] = sum(int(round(i["quantidade"] * i["valor_unit_centavos"])) for i in orcamento["itens"])
        return orcamento

    def salvar_orcamento(self, ator: Ator, dados: dict, orcamento_id: str | None = None) -> dict:
        ator.exigir("orcamentos", "editar" if orcamento_id else "criar")
        if orcamento_id:
            self.obter_orcamento(ator, orcamento_id)  # precisa estar na parte da igreja de quem edita
        contato_id = dados.get("contato_id")
        if (not contato_id or not self.banco.um("SELECT 1 AS x FROM contatos WHERE id=? AND empresa_id=?", (contato_id, ator.empresa))
                or not self._contato_no_alcance(ator, contato_id)):
            raise ErroNegocio("Escolha o nome (cliente) do orçamento.")
        itens_entrada = dados.get("itens") or []
        if not isinstance(itens_entrada, list) or not itens_entrada:
            raise ErroNegocio("Adicione pelo menos um item.")
        itens = []
        com_valores = self._com_valores(ator.empresa)
        for item in itens_entrada[:50]:
            servico = None
            if item.get("servico_id"):
                servico = self.banco.um("SELECT * FROM servicos WHERE id=? AND empresa_id=?", (item["servico_id"], ator.empresa))
                if not servico:
                    raise ErroNegocio("Serviço inválido no orçamento.")
            try:
                quantidade = float(str(item.get("quantidade", 1)).replace(",", "."))
            except ValueError:
                raise ErroNegocio("Quantidade inválida.") from None
            if not 0 < quantidade <= 100000:
                raise ErroNegocio("A quantidade precisa ser maior que zero.")
            valor = item.get("valor_unit")
            valor_centavos = centavos(valor) if valor not in (None, "") else (servico["preco_centavos"] if servico else 0)
            if not com_valores:
                valor_centavos = 0
            descricao = _texto(item.get("descricao") or (servico["nome"] if servico else ""), "descrição do item", maximo=200)
            itens.append((servico["id"] if servico else None, descricao, quantidade, valor_centavos))
        subtotal = sum(int(round(q * v)) for _s, _d, q, v in itens)
        desconto = centavos(dados.get("desconto", 0)) if com_valores else 0
        if desconto > subtotal:
            raise ErroNegocio("O desconto não pode ser maior que o valor dos itens.")
        validade = _data(dados.get("validade") or (date.today() + timedelta(days=7)).isoformat(), "validade")
        descricao = _texto(dados.get("descricao"), "descrição", False, 2000)
        total = subtotal - desconto
        with self.banco.transacao() as c:
            if orcamento_id:
                atual = c.execute("SELECT status FROM orcamentos WHERE id=? AND empresa_id=?", (orcamento_id, ator.empresa)).fetchone()
                if not atual:
                    raise NaoEncontrado("Orçamento não encontrado.")
                if atual["status"] in ("aprovado",):
                    raise ErroNegocio("Orçamento aprovado não pode ser alterado. Crie um novo.")
                c.execute(
                    "UPDATE orcamentos SET contato_id=?, descricao=?, validade=?, desconto_centavos=?, total_centavos=?, atualizado_em=? WHERE id=?",
                    (contato_id, descricao, validade, desconto, total, agora(), orcamento_id),
                )
                c.execute("DELETE FROM orcamento_itens WHERE orcamento_id=?", (orcamento_id,))
            else:
                orcamento_id = novo_id()
                numero = self.banco.proximo_numero(c, ator.empresa, "orcamento", 1001)
                c.execute(
                    """INSERT INTO orcamentos(id, empresa_id, numero, contato_id, conversa_id, descricao, validade, status,
                       desconto_centavos, total_centavos, criado_por, criado_em, atualizado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (orcamento_id, ator.empresa, numero, contato_id, dados.get("conversa_id") or None, descricao, validade, "rascunho",
                     desconto, total, ator.usuario_id, agora(), agora()),
                )
            for servico_id, descricao_item, quantidade, valor_centavos in itens:
                c.execute(
                    "INSERT INTO orcamento_itens(id, empresa_id, orcamento_id, servico_id, descricao, quantidade, valor_unit_centavos) VALUES (?,?,?,?,?,?,?)",
                    (novo_id(), ator.empresa, orcamento_id, servico_id, descricao_item, quantidade, valor_centavos),
                )
        self.auditar(ator, "orcamento.salvar", orcamento_id, {"total": total})
        return self.obter_orcamento(ator, orcamento_id)

    def mudar_status_orcamento(self, ator: Ator, orcamento_id: str, status: str) -> dict:
        ator.exigir("orcamentos", "editar")
        orcamento = self.obter_orcamento(ator, orcamento_id)
        if status not in STATUS_ORCAMENTO or status not in TRANSICOES_ORCAMENTO.get(orcamento["status"], ()):
            raise ErroNegocio(f"Não é possível mudar de '{orcamento['status']}' para '{status}'.")
        self._aplicar_status_orcamento(orcamento, status)
        self.auditar(ator, "orcamento.status", orcamento_id, {"status": status})
        return self.obter_orcamento(ator, orcamento_id)

    def _aplicar_status_orcamento(self, orcamento: dict, status: str) -> None:
        campos = {"enviado": ", enviado_em=:agora", "aprovado": ", decidido_em=:agora", "recusado": ", decidido_em=:agora"}
        self.banco.executar(
            f"UPDATE orcamentos SET status=:status, atualizado_em=:agora{campos.get(status, '')} WHERE id=:id",
            {"status": status, "agora": agora(), "id": orcamento["id"]},
        )
        if status in ("aprovado", "recusado"):
            self.disparar_evento(orcamento["empresa_id"], f"orcamento.{status}", {"id": orcamento["id"], "numero": orcamento["numero"]})
            nome_doc, sigla = self._rotulo_solicitacao()
            valor_txt = f" de {moeda(orcamento['total_centavos'])}" if self._com_valores(orcamento["empresa_id"]) else ""
            situacao = ("aprovada" if status == "aprovado" else "recusada") if sigla == "SOL" else status
            self._novo_alerta(orcamento["empresa_id"], f"orcamento:{orcamento['id']}:{status}", "orcamento",
                              "info" if status == "aprovado" else "atencao",
                              f"{nome_doc} {sigla}-{orcamento['numero']} {situacao}",
                              f"{orcamento.get('contato_nome', 'A pessoa')} {'aprovou' if status == 'aprovado' else 'recusou'} {'a solicitação' if sigla == 'SOL' else 'o orçamento'}{valor_txt}.",
                              orcamento["id"])

    def texto_orcamento(self, orcamento: dict, config: dict) -> str:
        nome_doc, sigla = self._rotulo_solicitacao()
        com_valores = self._com_valores(orcamento["empresa_id"])
        linhas = [f"*{config['empresa_nome']}* — {nome_doc} {sigla}-{orcamento['numero']}", ""]
        for item in orcamento["itens"]:
            qtd = f"{item['quantidade']:g}".replace(".", ",")
            linhas.append(f"• {item['descricao']} — {qtd} x {moeda(item['valor_unit_centavos'])}" if com_valores
                          else f"• {item['descricao']}" + (f" ({qtd})" if item["quantidade"] != 1 else ""))
        if com_valores and orcamento["desconto_centavos"]:
            linhas.append(f"Desconto: {moeda(orcamento['desconto_centavos'])}")
        linhas += [""] + ([f"*Total: {moeda(orcamento['total_centavos'])}*"] if com_valores else []) + [
            f"{'Prazo' if sigla == 'SOL' else 'Validade'}: {datetime.fromisoformat(orcamento['validade']).strftime('%d/%m/%Y')}"]
        if orcamento.get("descricao"):
            linhas += ["", orcamento["descricao"]]
        return "\n".join(linhas)

    def enviar_orcamento(self, ator: Ator, orcamento_id: str) -> dict:
        """Envia pelo WhatsApp oficial quando configurado. Sem canal
        configurado, devolve um link do WhatsApp (wa.me) já com o texto."""
        ator.exigir("orcamentos", "enviar")
        orcamento = self.obter_orcamento(ator, orcamento_id)
        if orcamento["status"] in ("aprovado", "recusado"):
            raise ErroNegocio("Este orçamento já foi decidido pelo cliente.")
        if orcamento["status"] == "vencido":
            raise ErroNegocio("Orçamento vencido. Volte para rascunho e ajuste a validade.")
        config = self.obter_config(ator.empresa)
        texto = self.texto_orcamento(orcamento, config)
        destino = orcamento["contato_whatsapp"]
        resultado = {"enviado_pelo_sistema": False, "link": None}
        if destino and self._canal_whatsapp_ativo(ator.empresa):
            conversa = self.banco.um(
                "SELECT * FROM conversas WHERE contato_id=? AND canal='whatsapp' AND status<>'resolvido' ORDER BY criada_em DESC LIMIT 1",
                (orcamento["contato_id"],),
            ) or self._nova_conversa(ator.empresa, orcamento["contato_id"], "whatsapp")
            mensagem = self._gravar_mensagem(conversa, "saida", "usuario", texto, autor_id=ator.usuario_id)
            self._entregar(conversa, mensagem, texto, [])
            enviada = self.banco.um("SELECT status_entrega, erro FROM mensagens WHERE id=?", (mensagem["id"],))
            if enviada and enviada["status_entrega"] == "falhou":
                raise ErroNegocio(f"O WhatsApp recusou o envio: {enviada['erro']}")
            resultado["enviado_pelo_sistema"] = True
        elif destino:
            resultado["link"] = "https://wa.me/" + destino + "?text=" + urllib.parse.quote(texto)
        else:
            raise ErroNegocio("Este nome não tem telefone/WhatsApp cadastrado.")
        if orcamento["status"] in ("rascunho", "enviado"):
            self._aplicar_status_orcamento(orcamento, "enviado")
        self.auditar(ator, "orcamento.enviar", orcamento_id, resultado)
        return {**resultado, "orcamento": self.obter_orcamento(ator, orcamento_id)}

    def html_impressao_orcamento(self, ator: Ator, orcamento_id: str) -> str:
        portal = ator.perfil == "cliente"
        orcamento = self.obter_orcamento(ator, orcamento_id, portal=portal)
        config = self.obter_config(ator.empresa)
        e = html.escape
        logo = f'<img class="logo" src="{e(config["logo"])}" alt="">' if config.get("logo") else ""
        nome_doc, sigla = self._rotulo_solicitacao()
        com_valores = self._com_valores(ator.empresa)
        partes = []
        for item in orcamento["itens"]:
            quantidade = f"{item['quantidade']:g}".replace(".", ",")
            total_item = moeda(int(round(item["quantidade"] * item["valor_unit_centavos"])))
            partes.append(
                f"<tr><td>{e(item['descricao'])}</td><td class='n'>{e(quantidade)}</td>"
                + (f"<td class='n'>{e(moeda(item['valor_unit_centavos']))}</td><td class='n'>{e(total_item)}</td>" if com_valores else "")
                + "</tr>"
            )
        linhas = "".join(partes)
        validade = datetime.fromisoformat(orcamento["validade"]).strftime("%d/%m/%Y")
        emissao = (para_datahora(orcamento["criado_em"]) or datetime.now(timezone.utc)).strftime("%d/%m/%Y")
        desconto = f"<tr><td colspan=3>Desconto</td><td class='n'>- {e(moeda(orcamento['desconto_centavos']))}</td></tr>" if orcamento["desconto_centavos"] else ""
        if com_valores:
            cabecalho = "<th>Item</th><th class='n'>Qtd.</th><th class='n'>Valor unit.</th><th class='n'>Total</th>"
            rodape = (f"<tfoot><tr><td colspan=3>Subtotal</td><td class='n'>{e(moeda(orcamento['subtotal_centavos']))}</td></tr>{desconto}"
                      f"<tr class=\"total\"><td colspan=3>Total</td><td class='n'>{e(moeda(orcamento['total_centavos']))}</td></tr></tfoot>")
        else:
            cabecalho, rodape = "<th>Item</th><th class='n'>Qtd.</th>", ""
        return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{sigla}-{orcamento['numero']}</title>
<link rel="stylesheet" href="/static/css/impressao.css"></head><body>
<header>{logo}<div><h1>{e(config['empresa_nome'])}</h1><p>{e(config['nome_sistema'])}</p></div>
<div class="num"><b>{nome_doc} {sigla}-{orcamento['numero']}</b><br>Emissão: {emissao}<br>{"Prazo" if sigla == "SOL" else "Validade"}: {validade}</div></header>
<section><h2>{"Pessoa" if sigla == "SOL" else "Cliente"}</h2><p><b>{e(orcamento['contato_nome'])}</b><br>{e(orcamento.get('contato_telefone') or '')} {e(orcamento.get('contato_email') or '')}</p></section>
{f"<section><h2>Descrição</h2><p>{e(orcamento['descricao'])}</p></section>" if orcamento.get('descricao') else ''}
<table><thead><tr>{cabecalho}</tr></thead>
<tbody>{linhas}</tbody>{rodape}</table>
<p class="rodape">Situação: {e(orcamento['status'].replace('_', ' '))}. Documento gerado pelo {e(config['nome_sistema'])}.</p>
<p class="acoes"><button id="imprimir">Salvar como PDF / Imprimir</button></p>
<script src="/static/js/impressao.js"></script></body></html>"""

    def portal_decidir_orcamento(self, ator: Ator, orcamento_id: str, aprovar: bool) -> dict:
        ator.exigir("portal", "decidir_orcamento")
        orcamento = self.obter_orcamento(ator, orcamento_id, portal=True)
        if orcamento["status"] not in ("enviado", "em_analise"):
            raise ErroNegocio("Este orçamento não está aguardando a sua decisão.")
        self._aplicar_status_orcamento(orcamento, "aprovado" if aprovar else "recusado")
        self.auditar(ator, "portal.orcamento", orcamento_id, {"aprovado": aprovar})
        return self.obter_orcamento(ator, orcamento_id, portal=True)

    # ================================================================ AGENDA
    def _limpar_agenda(self, ator: Ator, dados: dict, atual: dict | None = None) -> dict:
        atual = atual or {}
        titulo = _texto(dados.get("titulo", atual.get("titulo")), "título", maximo=120)
        inicio = para_datahora(dados.get("inicio", atual.get("inicio")))
        fim = para_datahora(dados.get("fim", atual.get("fim"))) if dados.get("fim", atual.get("fim")) else None
        if not inicio:
            raise ErroNegocio("Informe a data e hora de início.")
        if not fim:
            fim = inicio + timedelta(minutes=int(dados.get("duracao_minutos") or 60))
        if fim <= inicio:
            raise ErroNegocio("O fim precisa ser depois do início.")
        status = dados.get("status", atual.get("status", "agendado"))
        if status not in STATUS_AGENDA:
            raise ErroNegocio("Status inválido.")
        contato_id = dados.get("contato_id", atual.get("contato_id")) or None
        if contato_id and (not self.banco.um("SELECT 1 AS x FROM contatos WHERE id=? AND empresa_id=?", (contato_id, ator.empresa))
                           or not self._contato_no_alcance(ator, contato_id)):
            raise ErroNegocio("Nome inválido.")
        fila_id = dados.get("fila_id", atual.get("fila_id")) or None
        if fila_id and not self.banco.um("SELECT 1 AS x FROM filas WHERE id=? AND empresa_id=?", (fila_id, ator.empresa)):
            raise ErroNegocio("Equipe inválida.")
        responsavel_id = dados.get("responsavel_id", atual.get("responsavel_id")) or None
        if responsavel_id and (not self.banco.um("SELECT 1 AS x FROM usuarios WHERE id=? AND empresa_id=? AND perfil<>'cliente'", (responsavel_id, ator.empresa))
                               or not self._usuario_no_alcance(ator, responsavel_id)):
            raise ErroNegocio("Responsável inválido.")
        lembrete = int(dados.get("lembrete_minutos", atual.get("lembrete_minutos", 60)) or 0)
        return {
            "titulo": titulo, "inicio": inicio.isoformat(timespec="minutes"), "fim": fim.isoformat(timespec="minutes"),
            "status": status, "contato_id": contato_id, "fila_id": fila_id, "responsavel_id": responsavel_id,
            "observacao": _texto(dados.get("observacao", atual.get("observacao")), "observação", False, 500),
            "lembrete_minutos": max(0, min(lembrete, 10080)),
        }

    def _conflitos_agenda(self, empresa_id: str, valores: dict, ignorar_id: str | None = None) -> list[dict]:
        if not valores["responsavel_id"] or valores["status"] == "cancelado":
            return []
        candidatos = self.banco.todos(
            "SELECT id, titulo, inicio, fim FROM agenda WHERE empresa_id=? AND responsavel_id=? AND status<>'cancelado' AND id<>?",
            (empresa_id, valores["responsavel_id"], ignorar_id or ""),
        )
        inicio, fim = para_datahora(valores["inicio"]), para_datahora(valores["fim"])
        return [c for c in candidatos if para_datahora(c["inicio"]) < fim and para_datahora(c["fim"]) > inicio]

    def listar_agenda(self, ator: Ator, de: str | None = None, ate: str | None = None) -> list[dict]:
        ator.exigir("agenda", "ver")
        sql = """SELECT a.*, c.nome AS contato_nome, f.nome AS fila_nome, u.nome AS responsavel_nome FROM agenda a
                 LEFT JOIN contatos c ON c.id=a.contato_id LEFT JOIN filas f ON f.id=a.fila_id LEFT JOIN usuarios u ON u.id=a.responsavel_id
                 WHERE a.empresa_id=?"""
        parametros: list = [ator.empresa]
        if de:
            sql += " AND a.fim >= ?"
            parametros.append(de)
        if ate:
            sql += " AND a.inicio <= ?"
            parametros.append(ate)
        linhas = self.banco.todos(sql + " ORDER BY a.inicio LIMIT 2000", parametros)
        return [a for a in linhas if self._agenda_no_alcance(ator, a)][:500]

    def salvar_agendamento(self, ator: Ator, dados: dict, agendamento_id: str | None = None, forcar: bool = False) -> dict:
        ator.exigir("agenda", "editar" if agendamento_id else "criar")
        atual = None
        if agendamento_id:
            atual = self.banco.um("SELECT * FROM agenda WHERE id=? AND empresa_id=?", (agendamento_id, ator.empresa))
            if not atual or not self._agenda_no_alcance(ator, atual):
                raise NaoEncontrado("Agendamento não encontrado.")
        valores = self._limpar_agenda(ator, dados, atual)
        conflitos = self._conflitos_agenda(ator.empresa, valores, agendamento_id)
        if conflitos and not forcar:
            nomes = ", ".join(f"{c['titulo']} ({c['inicio'][11:16]})" for c in conflitos[:3])
            raise Conflito(f"Conflito de horário com: {nomes}. Confirme para agendar mesmo assim.")
        if agendamento_id:
            reset_lembrete = atual["inicio"] != valores["inicio"]
            self.banco.executar(
                """UPDATE agenda SET titulo=:titulo, inicio=:inicio, fim=:fim, status=:status, contato_id=:contato_id, fila_id=:fila_id,
                   responsavel_id=:responsavel_id, observacao=:observacao, lembrete_minutos=:lembrete_minutos,
                   lembrete_enviado=CASE WHEN :reset THEN 0 ELSE lembrete_enviado END WHERE id=:id""",
                {**valores, "reset": 1 if reset_lembrete else 0, "id": agendamento_id},
            )
        else:
            agendamento_id = novo_id()
            self.banco.executar(
                """INSERT INTO agenda(id, empresa_id, titulo, inicio, fim, contato_id, fila_id, responsavel_id, observacao, status,
                   lembrete_minutos, criado_em, unidade_id) VALUES (:id,:empresa,:titulo,:inicio,:fim,:contato_id,:fila_id,:responsavel_id,:observacao,
                   :status,:lembrete_minutos,:agora,:unidade)""",
                {**valores, "id": agendamento_id, "empresa": ator.empresa, "agora": agora(), "unidade": self._unidade_do_lancamento(ator)},
            )
        self.auditar(ator, "agenda.salvar", agendamento_id, {"inicio": valores["inicio"], "conflito_aceito": bool(conflitos)})
        return next(a for a in self.listar_agenda(ator) if a["id"] == agendamento_id)
