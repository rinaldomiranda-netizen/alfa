"""Acréscimos: recuperar senha, backup automático, termos/LGPD, aviso no celular (push), gráficos, relatórios,
avaliações das lojas e planos/mensalidade das empresas parceiras."""
from __future__ import annotations

import csv
import io
import json
import secrets
import smtplib
import sqlite3
import ssl
from datetime import timedelta
from email.message import EmailMessage

from . import push, seguranca
from .integracoes import telefone_whatsapp
from .nucleo import Ator, ErroNegocio, NaoEncontrado, SemPermissao, centavos, inteiro, iso, ler_data, novo_id, real, texto

VERSAO_TERMOS = "2026-10-03"
MINUTOS_CODIGO = 15
DIAS_BACKUP = 14


class ExtrasMixin:
    # ================================================================ E-MAIL (SMTP — pronto para ativar)
    def _email_cfg(self) -> dict | None:
        c = self.ler_integracao("email")
        return c if c.get("ligado") and c.get("servidor") and c.get("remetente") else None

    def enviar_email(self, para: str, assunto: str, corpo: str) -> bool:
        c = self._email_cfg()
        if not c:
            return False
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = c["remetente"], para, assunto
        msg.set_content(corpo)
        porta = int(c.get("porta") or 587)
        try:
            if porta == 465:
                s = smtplib.SMTP_SSL(c["servidor"], porta, timeout=12, context=ssl.create_default_context())
            else:
                s = smtplib.SMTP(c["servidor"], porta, timeout=12)
                s.starttls(context=ssl.create_default_context())
            if c.get("usuario"):
                s.login(c["usuario"], c.get("senha") or "")
            s.send_message(msg)
            s.quit()
            return True
        except (OSError, smtplib.SMTPException) as e:
            self.registrar_erro("email", "SMTP", e)
            return False

    # ================================================================ ESQUECI MINHA SENHA
    def canais_recuperacao(self) -> dict:
        return {"email": self._email_cfg() is not None, "whatsapp": self._wa() is not None}

    def pedir_codigo_senha(self, email: str) -> dict:
        """Manda um código de 6 números por e-mail (ou WhatsApp). A resposta é sempre a mesma (não revela se o e-mail existe)."""
        resposta = {"ok": True, "mensagem": "Se o e-mail estiver cadastrado, enviamos um código de 6 números. Ele vale 15 minutos."}
        canais = self.canais_recuperacao()
        if not any(canais.values()):
            return {"ok": False, "mensagem": "O envio de código ainda não foi ativado. Peça para a sua loja ou para a equipe Sobrou+ redefinir a senha."}
        u = self.banco.um("SELECT * FROM usuarios WHERE email=? AND ativo=1 AND excluido_em IS NULL", ((email or "").strip().lower(),))
        if not u:
            return resposta
        recentes = self.banco.um("SELECT COUNT(*) AS n FROM codigos_senha WHERE usuario_id=? AND criado_em>?",
                                 (u["id"], iso(self.agora_dt() - timedelta(hours=1))))["n"]
        if recentes >= 5:
            return resposta
        codigo = f"{secrets.randbelow(1_000_000):06d}"
        self.banco.executar("UPDATE codigos_senha SET usado=1 WHERE usuario_id=? AND usado=0", (u["id"],))
        self.banco.executar("INSERT INTO codigos_senha(id, usuario_id, codigo_hash, expira_em, criado_em) VALUES (?,?,?,?,?)",
                            (novo_id(), u["id"], seguranca.hash_token(u["id"] + ":" + codigo),
                             iso(self.agora_dt() + timedelta(minutes=MINUTOS_CODIGO)), self.agora()))
        texto_msg = f"Seu código para criar uma nova senha no Sobrou+ é {codigo}. Vale por {MINUTOS_CODIGO} minutos. Se não foi você, ignore."
        enviado = canais["email"] and self.enviar_email(u["email"], "Sobrou+ — código para nova senha", texto_msg)
        if not enviado and canais["whatsapp"] and telefone_whatsapp(u["telefone"]):
            try:
                self._enviar_whatsapp(self._wa(), telefone_whatsapp(u["telefone"]), texto_msg)
            except Exception as e:  # noqa: BLE001
                self.registrar_erro("senha.whatsapp", "POST", e)
        self.auditar(Ator(u["id"], u["papel"], u["nome"], u["empresa_id"]), "usuario.pedir_codigo_senha", u["id"], empresa_id=u["empresa_id"])
        return resposta

    def redefinir_com_codigo(self, email: str, codigo: str, nova: str) -> dict:
        erro = ErroNegocio("Código inválido ou vencido. Peça um novo código.")
        u = self.banco.um("SELECT * FROM usuarios WHERE email=? AND ativo=1", ((email or "").strip().lower(),))
        if not u:
            raise erro
        c = self.banco.um("SELECT * FROM codigos_senha WHERE usuario_id=? AND usado=0 AND expira_em>? ORDER BY criado_em DESC",
                          (u["id"], self.agora()))
        if not c or c["tentativas"] >= 5:
            raise erro
        if seguranca.hash_token(u["id"] + ":" + (codigo or "").strip()) != c["codigo_hash"]:
            self.banco.executar("UPDATE codigos_senha SET tentativas=tentativas+1 WHERE id=?", (c["id"],))
            raise erro
        try:
            seguranca.validar_senha_nova(nova)
        except seguranca.SenhaFraca as e:
            raise ErroNegocio(str(e)) from e
        salt = seguranca.gerar_salt()
        self.banco.executar("UPDATE usuarios SET senha_hash=?, senha_salt=?, senha_iteracoes=?, trocar_senha=0, tentativas_falhas=0, bloqueado_ate=NULL WHERE id=?",
                            (seguranca.hash_senha(nova, salt), salt, seguranca.ITERACOES, u["id"]))
        self.banco.executar("UPDATE codigos_senha SET usado=1 WHERE id=?", (c["id"],))
        self.banco.executar("DELETE FROM sessoes WHERE usuario_id=?", (u["id"],))
        self.auditar(Ator(u["id"], u["papel"], u["nome"], u["empresa_id"]), "usuario.senha_por_codigo", u["id"], empresa_id=u["empresa_id"])
        return {"ok": True, "mensagem": "Senha trocada. Entre com a nova senha."}

    # ================================================================ BACKUP AUTOMÁTICO
    def fazer_backup(self) -> str:
        pasta = self.pasta / "backups"
        pasta.mkdir(exist_ok=True)
        nome = f"sobrou-{self.agora_dt().strftime('%Y%m%d-%H%M%S')}.db"
        origem = sqlite3.connect(str(self.banco.caminho))
        destino = sqlite3.connect(str(pasta / nome))
        try:
            origem.backup(destino)
        finally:
            destino.close()
            origem.close()
        for velho in sorted(pasta.glob("sobrou-*.db"))[:-DIAS_BACKUP]:
            velho.unlink(missing_ok=True)
        self.banco.executar("INSERT INTO config(chave, valor) VALUES ('ultimo_backup', ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (self.agora(),))
        return nome

    def backup_se_preciso(self) -> str | None:
        r = self.banco.um("SELECT valor FROM config WHERE chave='ultimo_backup'")
        if r and (self.agora_dt() - ler_data(r["valor"])) < timedelta(hours=24):
            return None
        return self.fazer_backup()

    def listar_backups(self, ator: Ator) -> list[dict]:
        ator.exigir("sistema", "ver")
        pasta = self.pasta / "backups"
        return [{"nome": p.name, "bytes": p.stat().st_size} for p in sorted(pasta.glob("sobrou-*.db"), reverse=True)] if pasta.exists() else []

    def arquivo_backup(self, ator: Ator, nome: str):
        ator.exigir("sistema", "ver")
        alvo = (self.pasta / "backups" / nome).resolve()
        if alvo.parent != (self.pasta / "backups").resolve() or not alvo.name.startswith("sobrou-") or not alvo.is_file():
            raise NaoEncontrado("Backup não encontrado.")
        self.auditar(ator, "backup.baixar", nome, empresa_id=None)
        return alvo

    # ================================================================ TERMOS E LGPD
    def registrar_aceite(self, usuario_id: str) -> None:
        self.banco.executar("UPDATE usuarios SET aceite_termos_em=? WHERE id=?", (f"{self.agora()} v{VERSAO_TERMOS}", usuario_id))

    def meus_dados(self, ator: Ator) -> dict:
        u = self.banco.um("SELECT id, nome, email, telefone, papel, criado_em, ultimo_acesso, aceite_termos_em FROM usuarios WHERE id=?", (ator.usuario_id,))
        return {"gerado_em": self.agora(), "conta": u,
                "pedidos": self.banco.todos("""SELECT p.numero, p.status, p.modo, p.total_centavos, p.criado_em, e.nome AS loja FROM pedidos p
                                               JOIN empresas e ON e.id=p.empresa_id WHERE p.cliente_id=? ORDER BY p.criado_em""", (ator.usuario_id,)),
                "avaliacoes": self.banco.todos("SELECT nota, comentario, criada_em FROM avaliacoes WHERE cliente_id=?", (ator.usuario_id,)),
                "avaliacoes_recebidas": self.banco.todos("SELECT nota, comentario, criada_em FROM avaliacoes_clientes WHERE cliente_id=?", (ator.usuario_id,)),
                "pontos_fidelidade": self.banco.um("SELECT COALESCE(SUM(pontos),0) AS total FROM pontos_fidelidade WHERE cliente_id=?", (ator.usuario_id,))["total"],
                "favoritos": self.banco.todos("SELECT e.nome FROM favoritos f JOIN empresas e ON e.id=f.empresa_id WHERE f.cliente_id=?", (ator.usuario_id,))}

    def excluir_minha_conta(self, ator: Ator, senha: str) -> dict:
        """LGPD: apaga os dados pessoais. Os pedidos ficam (obrigação fiscal), sem nome, e-mail ou telefone."""
        if ator.papel != "cliente":
            raise SemPermissao("Contas de empresa, entregador ou equipe são encerradas pelo administrador.")
        u = self.banco.um("SELECT * FROM usuarios WHERE id=?", (ator.usuario_id,))
        if not seguranca.conferir_senha(senha or "", u["senha_salt"], u["senha_hash"], int(u.get("senha_iteracoes") or 200_000)): 
            raise ErroNegocio("Senha incorreta.")
        abertos = self.banco.um("""SELECT COUNT(*) AS n FROM pedidos WHERE cliente_id=? AND status IN
                                   ('aguardando_pagamento','pago','recebido','preparando','pronto','aguardando_retirada','aguardando_entregador',
                                    'entregador_designado','em_coleta','em_rota','entregue')""", (u["id"],))["n"]
        if abertos:
            raise ErroNegocio("Você tem pedido em andamento. Espere concluir para excluir a conta.")
        anon = f"excluido-{u['id'][:8]}@sobrou.invalid"
        self.banco.executar("""UPDATE usuarios SET nome='Cliente excluído', email=?, telefone=NULL, ativo=0, excluido_em=?, senha_hash='-', senha_salt='00'
                               WHERE id=?""", (anon, self.agora(), u["id"]))
        for tabela in ("sessoes", "favoritos", "push_inscricoes"):
            col = "cliente_id" if tabela == "favoritos" else "usuario_id"
            self.banco.executar(f"DELETE FROM {tabela} WHERE {col}=?", (u["id"],))
        self.banco.executar("UPDATE pedidos SET endereco_entrega=NULL, entrega_lat=NULL, entrega_lng=NULL, observacao=NULL WHERE cliente_id=?", (u["id"],))
        self.banco.executar("DELETE FROM fila_mensagens WHERE usuario_id=?", (u["id"],))
        self.auditar(ator, "lgpd.excluir_conta", u["id"], empresa_id=None)
        return {"ok": True}

    # ================================================================ AVISO NO CELULAR (PUSH)
    def chave_push_publica(self) -> str | None:
        if not push.DISPONIVEL:
            return None
        r = self.banco.um("SELECT valor FROM config WHERE chave='vapid'")
        if r:
            return json.loads(r["valor"])["publica"]
        pem, pub = push.novas_chaves_vapid()
        self.banco.executar("INSERT OR IGNORE INTO config(chave, valor) VALUES ('vapid', ?)", (json.dumps({"privada": pem, "publica": pub}),))
        return json.loads(self.banco.um("SELECT valor FROM config WHERE chave='vapid'")["valor"])["publica"]

    def inscrever_push(self, ator: Ator, dados: dict) -> dict:
        if not push.DISPONIVEL:
            raise ErroNegocio("Aviso no celular indisponível neste servidor.")
        ep = texto(dados.get("endpoint"), 1000, True, "o endereço do aviso")
        if not ep.startswith("https://"):
            raise ErroNegocio("Inscrição inválida.")
        chaves = dados.get("keys") or {}
        self.banco.executar("""INSERT INTO push_inscricoes(id, usuario_id, endpoint, p256dh, auth, criada_em) VALUES (?,?,?,?,?,?)
                               ON CONFLICT(endpoint) DO UPDATE SET usuario_id=excluded.usuario_id, p256dh=excluded.p256dh, auth=excluded.auth""",
                            (novo_id(), ator.usuario_id, ep, texto(chaves.get("p256dh"), 200, True, "a chave"), texto(chaves.get("auth"), 100, True, "a chave"), self.agora()))
        return {"ok": True}

    def enfileirar_push(self, usuario_id: str | None, texto_msg: str, link: str | None = None, empresa_id: str | None = None,
                        papel_alvo: str | None = None, conn=None) -> None:
        if not push.DISPONIVEL:
            return
        sql = "INSERT INTO fila_mensagens(id, canal, usuario_id, telefone, texto, criada_em) VALUES (?,?,?,?,?,?)"
        exe = conn.execute if conn is not None else self.banco.executar
        alvos = [usuario_id] if usuario_id else []
        if not usuario_id and empresa_id:
            consulta = (lambda s, p: [dict(r) for r in conn.execute(s, p).fetchall()]) if conn is not None else self.banco.todos
            alvos = [u["id"] for u in consulta("SELECT id FROM usuarios WHERE empresa_id=? AND ativo=1 AND papel IN ('admin_empresa','operador_empresa')"
                                               + (" AND papel=?" if papel_alvo else ""), (empresa_id, papel_alvo) if papel_alvo else (empresa_id,))]
        consulta1 = (lambda s_, p_: conn.execute(s_, p_).fetchone()) if conn is not None else self.banco.um
        for uid in alvos:
            if consulta1("SELECT 1 AS x FROM push_inscricoes WHERE usuario_id=? LIMIT 1", (uid,)):  # só quem ligou o aviso no celular
                exe(sql, (novo_id(), "push", uid, link or "", texto_msg[:300], self.agora()))

    def enviar_fila_push(self, limite: int = 40, enviador=None) -> int:
        if not push.DISPONIVEL:
            return 0
        pub = self.chave_push_publica()
        pem = json.loads(self.banco.um("SELECT valor FROM config WHERE chave='vapid'")["valor"])["privada"]
        enviados = 0
        for m in self.banco.todos("SELECT * FROM fila_mensagens WHERE canal='push' AND status='pendente' ORDER BY criada_em LIMIT ?", (limite,)):
            inscricoes = self.banco.todos("SELECT * FROM push_inscricoes WHERE usuario_id=?", (m["usuario_id"],))
            ok = False
            for i in inscricoes:
                st = push.enviar(i, {"titulo": "Sobrou+", "texto": m["texto"], "link": m["telefone"] or ""}, pem, pub, enviador=enviador)
                if st in (404, 410):
                    self.banco.executar("DELETE FROM push_inscricoes WHERE id=?", (i["id"],))
                ok = ok or 200 <= st < 300
            self.banco.executar("UPDATE fila_mensagens SET status=?, enviada_em=?, tentativas=tentativas+1 WHERE id=?",
                                ("enviada" if ok else ("desligado" if not inscricoes else "falhou"), self.agora(), m["id"]))
            enviados += ok
        return enviados

    # ================================================================ GRÁFICOS E RELATÓRIOS
    def _escopo_rel(self, ator: Ator, empresa_id: str | None) -> tuple[str, tuple]:
        if ator.plataforma and not empresa_id:
            return "", ()
        return " AND p.empresa_id=?", (ator.empresa_alvo(empresa_id),)

    def graficos(self, ator: Ator, empresa_id: str | None = None, dias: int = 14) -> dict:
        ator.exigir("impacto", "ver")
        cond, par = self._escopo_rel(ator, empresa_id)
        dias = max(7, min(90, int(dias or 14)))
        inicio = (self.agora_dt() - timedelta(days=dias - 1)).replace(hour=0, minute=0, second=0)
        linhas = self.banco.todos(f"""SELECT substr(p.concluido_em,1,10) AS dia, COUNT(*) AS pedidos, SUM(p.peso_kg) AS kg,
                                             SUM(p.subtotal_centavos) AS vendas, SUM(p.normal_centavos-p.subtotal_centavos) AS economia
                                      FROM pedidos p WHERE p.status='concluido' AND p.concluido_em>=? {cond} GROUP BY dia""", (iso(inicio), *par))
        por_dia = {l["dia"]: l for l in linhas}
        serie = []
        for i in range(dias):
            d = (inicio + timedelta(days=i)).strftime("%Y-%m-%d")
            l = por_dia.get(d) or {}
            serie.append({"dia": d, "pedidos": l.get("pedidos") or 0, "kg": round(l.get("kg") or 0, 2),
                          "vendas_centavos": l.get("vendas") or 0, "economia_centavos": l.get("economia") or 0})
        categorias = self.banco.todos(f"""SELECT o.categoria, SUM(i.quantidade) AS unidades, SUM(i.peso_kg) AS kg FROM pedido_itens i
                                          JOIN pedidos p ON p.id=i.pedido_id JOIN ofertas o ON o.id=i.oferta_id
                                          WHERE p.status='concluido' AND p.concluido_em>=? {cond} GROUP BY o.categoria ORDER BY kg DESC""", (iso(inicio), *par))
        return {"serie": serie, "categorias": categorias}

    RELATORIOS = {
        "pedidos": ("Pedidos", ["numero", "criado_em", "loja", "cliente", "modo", "status", "subtotal", "entrega", "total", "taxa", "repasse", "kg"]),
        "ofertas": ("Ofertas", ["nome", "tipo", "categoria", "loja", "preco_normal", "preco_sobrou", "total", "vendida", "sobra", "doada", "status", "fim"]),
        "doacoes": ("Doações", ["proposta_em", "loja", "instituicao", "quantidade", "kg", "status", "coleta_responsavel", "destinada_em", "pessoas"]),
        "repasses": ("Repasses", ["criado_em", "loja", "pedidos", "bruto", "taxa", "valor", "status", "pago_em", "referencia"]),
        "avaliacoes": ("Avaliações", ["criada_em", "loja", "pedido", "nota", "comentario", "resposta"]),
    }

    def relatorio_csv(self, ator: Ator, tipo: str, empresa_id: str | None = None, de=None, ate=None) -> tuple[str, bytes]:
        if tipo not in self.RELATORIOS:
            raise NaoEncontrado("Relatório desconhecido.")
        if tipo in ("repasses",):
            ator.exigir("financeiro", "ver")
        else:
            ator.exigir("pedidos", "ver") if tipo != "doacoes" else ator.exigir("doacoes", "ver")
        cond, par = self._escopo_rel(ator, empresa_id)
        i = (ler_data(de) and iso(ler_data(de))) or "2000-01-01T00:00:00+00:00"
        f = (ler_data(ate) and iso(ler_data(ate) + timedelta(days=1))) or "2999-01-01T00:00:00+00:00"
        r = lambda c: f"{(c or 0) / 100:.2f}".replace(".", ",")  # noqa: E731
        if tipo == "pedidos":
            dados = [[p["numero"], p["criado_em"], p["loja"], p["cliente"], p["modo"], p["status"], r(p["subtotal_centavos"]), r(p["entrega_centavos"]),
                      r(p["total_centavos"]), r(p["taxa_centavos"]), r(p["repasse_centavos"]), str(p["peso_kg"]).replace(".", ",")]
                     for p in self.banco.todos(f"""SELECT p.*, e.nome AS loja, u.nome AS cliente FROM pedidos p JOIN empresas e ON e.id=p.empresa_id
                                                   JOIN usuarios u ON u.id=p.cliente_id WHERE p.criado_em>=? AND p.criado_em<? {cond} ORDER BY p.criado_em""", (i, f, *par))]
        elif tipo == "ofertas":
            dados = [[o["nome"], o["tipo"], o["categoria"], o["loja"], r(o["preco_normal_centavos"]), r(o["preco_centavos"]), o["quantidade_total"],
                      o["vendida"], o["expirada"], o["destinada"], o["status"], o["fim"]]
                     for o in self.banco.todos(f"""SELECT o.*, e.nome AS loja FROM ofertas o JOIN empresas e ON e.id=o.empresa_id
                                                   WHERE o.criada_em>=? AND o.criada_em<? {cond.replace('p.', 'o.')} ORDER BY o.criada_em""", (i, f, *par))]
        elif tipo == "doacoes":
            dados = [[d["proposta_em"], d["loja"], d["instituicao"], d["quantidade"], str(d["peso_kg"]).replace(".", ","), d["status"],
                      d["coleta_responsavel"] or "", d["destinada_em"] or "", d["pessoas_beneficiadas"] or ""]
                     for d in self.banco.todos(f"""SELECT d.*, e.nome AS loja, s.nome AS instituicao FROM doacoes d JOIN empresas e ON e.id=d.empresa_id
                                                   JOIN instituicoes s ON s.id=d.instituicao_id WHERE d.proposta_em>=? AND d.proposta_em<? {cond.replace('p.', 'd.')}
                                                   ORDER BY d.proposta_em""", (i, f, *par))]
        elif tipo == "repasses":
            dados = [[x["criado_em"], x["loja"], x["pedidos"], r(x["bruto_centavos"]), r(x["taxa_centavos"]), r(x["valor_centavos"]), x["status"],
                      x["pago_em"] or "", x["referencia"] or ""]
                     for x in self.banco.todos(f"""SELECT x.*, e.nome AS loja FROM repasses x JOIN empresas e ON e.id=x.empresa_id
                                                   WHERE x.criado_em>=? AND x.criado_em<? {cond.replace('p.', 'x.')} ORDER BY x.criado_em""", (i, f, *par))]
        else:
            dados = [[a["criada_em"], a["loja"], a["numero"], a["nota"], a["comentario"] or "", a["resposta"] or ""]
                     for a in self.banco.todos(f"""SELECT a.*, e.nome AS loja, p.numero FROM avaliacoes a JOIN empresas e ON e.id=a.empresa_id
                                                   JOIN pedidos p ON p.id=a.pedido_id WHERE a.criada_em>=? AND a.criada_em<? {cond.replace('p.empresa_id', 'a.empresa_id')}
                                                   ORDER BY a.criada_em""", (i, f, *par))]
        saida = io.StringIO()
        w = csv.writer(saida, delimiter=";")  # ";" abre direto no Excel em português
        w.writerow(self.RELATORIOS[tipo][1])
        # Texto que começa com = + - @ viraria fórmula no Excel: entra como texto comum.
        w.writerows([[("'" + v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v for v in linha]
                     for linha in dados])
        self.auditar(ator, "relatorio.baixar", tipo, {"linhas": len(dados)}, empresa_id=None if ator.plataforma else ator.empresa_id)
        return f"sobrou_{tipo}_{self.agora_dt().strftime('%Y%m%d')}.csv", ("﻿" + saida.getvalue()).encode("utf-8")

    # ================================================================ AVALIAÇÕES
    def avaliar_pedido(self, ator: Ator, pedido_id: str, nota, comentario=None) -> dict:
        n = inteiro(nota, "a nota", 1, 5)
        with self.banco.transacao() as c:
            p = self._uma(c, "SELECT * FROM pedidos WHERE id=?", (pedido_id,))
            if not p or p["cliente_id"] != ator.usuario_id:
                raise NaoEncontrado("Pedido não encontrado.")
            if p["status"] != "concluido":
                raise ErroNegocio("Você pode avaliar depois que o pedido for concluído.")
            if c.execute("SELECT id FROM avaliacoes WHERE pedido_id=?", (pedido_id,)).fetchone():
                raise ErroNegocio("Este pedido já foi avaliado.")
            c.execute("INSERT INTO avaliacoes(id, pedido_id, empresa_id, cliente_id, nota, comentario, criada_em) VALUES (?,?,?,?,?,?,?)",
                      (novo_id(), pedido_id, p["empresa_id"], ator.usuario_id, n, texto(comentario, 500), self.agora()))
            self.avisar(f"Nova avaliação: {'★' * n}{'☆' * (5 - n)} no pedido #{p['numero']}.", empresa_id=p["empresa_id"], conn=c)
        return {"ok": True}

    def avaliar_cliente_pedido(self, ator: Ator, pedido_id: str, nota, comentario=None) -> dict:
        """Empresa avalia o cliente apenas após uma compra concluída e uma única vez."""
        ator.exigir("pedidos", "operar")
        n = inteiro(nota, "a nota", 1, 5)
        with self.banco.transacao() as c:
            p = ator.conferir_empresa(self._uma(c, "SELECT * FROM pedidos WHERE id=?", (pedido_id,)), "Pedido")
            if p["status"] != "concluido":
                raise ErroNegocio("A avaliação do cliente fica disponível depois que o pedido for concluído.")
            if c.execute("SELECT id FROM avaliacoes_clientes WHERE pedido_id=?", (pedido_id,)).fetchone():
                raise ErroNegocio("Este cliente já foi avaliado neste pedido.")
            c.execute("INSERT INTO avaliacoes_clientes(id,pedido_id,empresa_id,cliente_id,nota,comentario,criada_em) VALUES (?,?,?,?,?,?,?)",
                      (novo_id(), pedido_id, p["empresa_id"], p["cliente_id"], n, texto(comentario, 500), self.agora()))
            self.avisar(f"A empresa avaliou sua compra #{p['numero']}: {'★' * n}{'☆' * (5 - n)}.",
                        usuario_id=p["cliente_id"], link=f"/#pedido/{pedido_id}", conn=c)
        self.auditar(ator, "avaliacao_cliente.criar", pedido_id, {"nota": n}, empresa_id=p["empresa_id"])
        return {"ok": True}

    def listar_avaliacoes_clientes(self, ator: Ator, empresa_id: str | None = None) -> dict:
        ator.exigir("pedidos", "ver")
        if ator.plataforma and not empresa_id:
            cond, par = "", ()
        else:
            cond, par = " WHERE a.empresa_id=?", (ator.empresa_alvo(empresa_id),)
        itens = self.banco.todos(f"""SELECT a.*, e.nome AS loja, p.numero, u.nome AS cliente
                                     FROM avaliacoes_clientes a JOIN empresas e ON e.id=a.empresa_id
                                     JOIN pedidos p ON p.id=a.pedido_id JOIN usuarios u ON u.id=a.cliente_id
                                     {cond} ORDER BY a.criada_em DESC LIMIT 200""", par)
        media = round(sum(a["nota"] for a in itens) / len(itens), 1) if itens else None
        return {"itens": itens, "media": media, "total": len(itens)}

    def minha_reputacao(self, ator: Ator) -> dict:
        if ator.papel != "cliente":
            raise SemPermissao("Esta área é só para contas de cliente.")
        a = self.banco.um("SELECT AVG(nota) AS media, COUNT(*) AS total FROM avaliacoes_clientes WHERE cliente_id=?", (ator.usuario_id,)) or {}
        p = self.banco.um("SELECT COALESCE(SUM(pontos),0) AS pontos FROM pontos_fidelidade WHERE cliente_id=?", (ator.usuario_id,)) or {}
        itens = self.banco.todos("""SELECT a.nota, a.comentario, a.criada_em, e.nome AS loja, ped.numero
                                   FROM avaliacoes_clientes a JOIN empresas e ON e.id=a.empresa_id
                                   JOIN pedidos ped ON ped.id=a.pedido_id WHERE a.cliente_id=?
                                   ORDER BY a.criada_em DESC LIMIT 50""", (ator.usuario_id,))
        return {"media": round(a["media"], 1) if a.get("media") is not None else None,
                "total": a.get("total", 0), "pontos": p.get("pontos", 0), "itens": itens}

    def responder_avaliacao(self, ator: Ator, avaliacao_id: str, resposta: str) -> dict:
        ator.exigir("pedidos", "operar")
        a = ator.conferir_empresa(self.banco.um("SELECT * FROM avaliacoes WHERE id=?", (avaliacao_id,)), "Avaliação")
        self.banco.executar("UPDATE avaliacoes SET resposta=?, respondida_em=? WHERE id=?", (texto(resposta, 500, True, "a resposta"), self.agora(), avaliacao_id))
        self.auditar(ator, "avaliacao.responder", avaliacao_id, empresa_id=a["empresa_id"])
        return {"ok": True}

    def notas_empresas(self) -> dict:
        return {r["empresa_id"]: {"media": round(r["media"], 1), "total": r["total"]}
                for r in self.banco.todos("SELECT empresa_id, AVG(nota) AS media, COUNT(*) AS total FROM avaliacoes GROUP BY empresa_id")}

    def listar_avaliacoes(self, ator: Ator, empresa_id: str | None = None) -> dict:
        ator.exigir("pedidos", "ver")
        cond, par = ("", ()) if (ator.plataforma and not empresa_id) else (" WHERE a.empresa_id=?", (ator.empresa_alvo(empresa_id),))
        itens = self.banco.todos(f"""SELECT a.*, e.nome AS loja, p.numero, u.nome AS cliente FROM avaliacoes a JOIN empresas e ON e.id=a.empresa_id
                                     JOIN pedidos p ON p.id=a.pedido_id JOIN usuarios u ON u.id=a.cliente_id {cond} ORDER BY a.criada_em DESC LIMIT 200""", par)
        media = round(sum(a["nota"] for a in itens) / len(itens), 1) if itens else None
        return {"itens": itens, "media": media, "total": len(itens)}

    def publico_avaliacoes(self, empresa_id: str) -> list[dict]:
        return self.banco.todos("""SELECT a.nota, a.comentario, a.resposta, a.criada_em FROM avaliacoes a WHERE a.empresa_id=?
                                   AND (a.comentario IS NOT NULL OR a.nota>=4) ORDER BY a.criada_em DESC LIMIT 20""", (empresa_id,))

    # ================================================================ PLANOS E MENSALIDADE
    def garantir_planos(self) -> None:
        if self.banco.um("SELECT id FROM planos LIMIT 1"):
            return
        for nome, desc, mensal, taxa, limite, destaque in (
                ("Essencial", "Sem mensalidade. Paga só a taxa sobre o que vender.", 0, 15.0, 5, 0),
                ("Profissional", "Mensalidade fixa, taxa menor e ofertas sem limite.", 9900, 10.0, None, 0),
                ("Destaque", "Taxa menor e lojas aparecendo primeiro no app.", 19900, 8.0, None, 1)):
            self.banco.executar("""INSERT INTO planos(id, nome, descricao, mensalidade_centavos, taxa_percentual, limite_ofertas, destaque, criado_em)
                                   VALUES (?,?,?,?,?,?,?,?)""", (novo_id(), nome, desc, mensal, taxa, limite, destaque, self.agora()))

    def listar_planos(self, ator: Ator | None = None) -> list[dict]:
        self.garantir_planos()
        linhas = self.banco.todos("""SELECT pl.*, (SELECT COUNT(*) FROM empresas e WHERE e.plano_id=pl.id) AS empresas FROM planos pl
                                     WHERE pl.ativo=1 OR ? ORDER BY pl.mensalidade_centavos""", (1 if ator and ator.plataforma else 0,))
        return [{**p, "destaque": bool(p["destaque"])} for p in linhas]

    def salvar_plano(self, ator: Ator, dados: dict, plano_id: str | None = None) -> dict:
        ator.exigir("empresas", "aprovar")
        valores = (texto(dados.get("nome"), 60, True, "o nome do plano"), texto(dados.get("descricao"), 200),
                   centavos(dados.get("mensalidade"), "a mensalidade"), real(dados.get("taxa_percentual"), "a taxa", 0, 60, True),
                   inteiro(dados.get("limite_ofertas"), "o limite", 1, 10000) if dados.get("limite_ofertas") not in (None, "") else None,
                   1 if dados.get("destaque") in (True, 1, "1", "on", "true") else 0, 0 if dados.get("ativo") in (False, 0, "0") else 1)
        if plano_id:
            self.banco.executar("UPDATE planos SET nome=?, descricao=?, mensalidade_centavos=?, taxa_percentual=?, limite_ofertas=?, destaque=?, ativo=? WHERE id=?",
                                (*valores, plano_id))
        else:
            plano_id = novo_id()
            self.banco.executar("""INSERT INTO planos(nome, descricao, mensalidade_centavos, taxa_percentual, limite_ofertas, destaque, ativo, id, criado_em)
                                   VALUES (?,?,?,?,?,?,?,?,?)""", (*valores, plano_id, self.agora()))
        self.auditar(ator, "plano.salvar", plano_id, {"nome": valores[0]}, empresa_id=None)
        return self.banco.um("SELECT * FROM planos WHERE id=?", (plano_id,))

    def definir_plano(self, ator: Ator, empresa_id: str, plano_id: str | None) -> dict:
        ator.exigir("empresas", "aprovar")
        self.obter_empresa(ator, empresa_id)
        if plano_id and not self.banco.um("SELECT id FROM planos WHERE id=?", (plano_id,)):
            raise NaoEncontrado("Plano não encontrado.")
        self.banco.executar("UPDATE empresas SET plano_id=? WHERE id=?", (plano_id or None, empresa_id))
        self.auditar(ator, "empresa.plano", empresa_id, {"plano": plano_id}, empresa_id=empresa_id)
        return self.obter_empresa(ator, empresa_id)

    def plano_da_empresa(self, empresa: dict) -> dict | None:
        if not empresa.get("plano_id"):
            return None
        return self.banco.um("SELECT * FROM planos WHERE id=?", (empresa["plano_id"],))

    def gerar_faturas(self) -> int:
        """Todo mês (rotina): uma fatura por empresa com plano de mensalidade. Vence no dia 10."""
        comp = self.agora_dt().strftime("%Y-%m")
        n = 0
        for e in self.banco.todos("""SELECT e.id, pl.id AS plano_id, pl.mensalidade_centavos FROM empresas e JOIN planos pl ON pl.id=e.plano_id
                                     WHERE e.aprovada=1 AND e.ativa=1 AND e.demonstracao=0 AND pl.mensalidade_centavos>0"""):
            n += self.banco.executar("""INSERT OR IGNORE INTO faturas(id, empresa_id, plano_id, competencia, valor_centavos, vence_em, criada_em)
                                        VALUES (?,?,?,?,?,?,?)""", (novo_id(), e["id"], e["plano_id"], comp, e["mensalidade_centavos"], f"{comp}-10", self.agora()))
        return n

    def listar_faturas(self, ator: Ator, empresa_id: str | None = None) -> list[dict]:
        ator.exigir("financeiro", "ver")
        if ator.plataforma and not empresa_id:
            return self.banco.todos("""SELECT f.*, e.nome AS empresa, pl.nome AS plano FROM faturas f JOIN empresas e ON e.id=f.empresa_id
                                       LEFT JOIN planos pl ON pl.id=f.plano_id ORDER BY f.competencia DESC, e.nome""")
        return self.banco.todos("""SELECT f.*, e.nome AS empresa, pl.nome AS plano FROM faturas f JOIN empresas e ON e.id=f.empresa_id
                                   LEFT JOIN planos pl ON pl.id=f.plano_id WHERE f.empresa_id=? ORDER BY f.competencia DESC""", (ator.empresa_alvo(empresa_id),))

    def marcar_fatura_paga(self, ator: Ator, fatura_id: str, referencia: str) -> dict:
        ator.exigir("financeiro", "repassar")
        if not ator.plataforma:
            raise SemPermissao("Só a equipe Sobrou+ confirma o pagamento da mensalidade.")
        f = ator.conferir_empresa(self.banco.um("SELECT * FROM faturas WHERE id=?", (fatura_id,)), "Fatura")
        if f["status"] == "paga":
            raise ErroNegocio("Esta fatura já está paga.")
        self.banco.executar("UPDATE faturas SET status='paga', paga_em=?, referencia=? WHERE id=?",
                            (self.agora(), texto(referencia, 120, True, "o comprovante"), fatura_id))
        self.auditar(ator, "fatura.paga", fatura_id, empresa_id=f["empresa_id"])
        return self.banco.um("SELECT * FROM faturas WHERE id=?", (fatura_id,))
