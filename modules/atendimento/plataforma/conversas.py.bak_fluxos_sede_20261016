"""Nomes (contatos), filas, equipe e conversas (caixa de entrada)."""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone

from . import fluxos as motor
from .db import agora, para_datahora, somar_minutos
from .nucleo import Ator, ErroNegocio, NaoEncontrado, _texto, novo_id

STATUS_CONVERSA = ("novo", "robo", "aguardando", "em_atendimento", "resolvido")
CANAIS = ("web", "whatsapp", "portal", "interno")
STATUS_CONTATO = ("novo", "ativo", "inativo")
_SO_DIGITOS = re.compile(r"\D+")


def normalizar_telefone(valor: str | None) -> str | None:
    digitos = _SO_DIGITOS.sub("", valor or "")
    if not digitos:
        return None
    if len(digitos) in (10, 11):  # número brasileiro sem o 55
        digitos = "55" + digitos
    return digitos


def prioridade_sla(sla_vence_em: str | None, criada_em: str | None) -> tuple[str, int | None]:
    """(prioridade, segundos restantes). Urgente = vencido ou menos de 25% do prazo."""
    vence = para_datahora(sla_vence_em)
    if not vence:
        return "normal", None
    agora_dt = datetime.now(timezone.utc)
    restante = int((vence - agora_dt).total_seconds())
    inicio = para_datahora(criada_em) or agora_dt
    total = max(1, int((vence - inicio).total_seconds()))
    if restante <= 0 or restante < total * 0.25:
        return "urgente", restante
    if restante < total * 0.5:
        return "alta", restante
    return "normal", restante


class ConversasMixin:
    # ================================================================ NOMES
    @staticmethod
    def _contato_publico(linha: dict) -> dict:
        return {**linha, "tags": json.loads(linha.get("tags") or "[]"), "dados": json.loads(linha.get("dados") or "{}")}

    def _limpar_contato(self, dados: dict, atual: dict | None = None) -> dict:
        atual = atual or {}
        tags = dados.get("tags", atual.get("tags", []))
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.replace(";", ",").split(",")]
        tags = sorted({str(t).strip()[:30] for t in tags if str(t).strip()})[:15]
        status = dados.get("status", atual.get("status", "novo"))
        if status not in STATUS_CONTATO:
            raise ErroNegocio("Status inválido.")
        telefone = normalizar_telefone(dados.get("telefone", atual.get("telefone")))
        whatsapp = normalizar_telefone(dados.get("whatsapp", atual.get("whatsapp"))) or telefone
        email = (dados.get("email", atual.get("email")) or "").strip() or None
        if email and ("@" not in email or len(email) > 160):
            raise ErroNegocio("E-mail inválido.")
        return {
            "nome": _texto(dados.get("nome", atual.get("nome")), "nome", maximo=120),
            "telefone": telefone, "whatsapp": whatsapp, "email": email,
            "tags": json.dumps(tags, ensure_ascii=False),
            "observacoes": (_texto(dados.get("observacoes", atual.get("observacoes")), "observações", False, 2000)),
            "status": status,
        }

    def listar_contatos(self, ator: Ator, busca: str = "", tag: str = "", limite: int = 200) -> list[dict]:
        ator.exigir("contatos", "ver")
        sql = "SELECT * FROM contatos WHERE empresa_id=?"
        parametros: list = [ator.empresa]
        if busca:
            sql += " AND (nome LIKE ? OR telefone LIKE ? OR email LIKE ? OR tags LIKE ?)"
            termo = f"%{busca.strip()}%"
            parametros += [termo, termo, termo, termo]
        if tag:
            sql += " AND tags LIKE ?"
            parametros.append(f'%"{tag}"%')
        limite = max(1, min(limite, 1000))
        restrito = self._escopo_cache(ator) is not None  # parte da igreja (não é a Sede): filtra pela hierarquia
        sql += " ORDER BY COALESCE(ultimo_contato, criado_em) DESC LIMIT ?"
        parametros.append(5000 if restrito else limite)
        linhas = self.banco.todos(sql, parametros)
        if restrito:
            linhas = [c for c in linhas if self._contato_no_alcance(ator, c)][:limite]
        return [self._contato_publico(c) for c in linhas]

    def obter_contato(self, ator: Ator, contato_id: str) -> dict:
        ator.exigir("contatos", "ver")
        contato = self.banco.um("SELECT * FROM contatos WHERE id=? AND empresa_id=?", (contato_id, ator.empresa))
        if not contato or not self._contato_no_alcance(ator, contato):
            raise NaoEncontrado("Nome não encontrado.")
        historico = self.banco.todos(
            "SELECT id, numero, canal, status, criada_em, resolvida_em, avaliacao FROM conversas WHERE contato_id=? ORDER BY criada_em DESC LIMIT 50",
            (contato_id,),
        )
        orcamentos = self.banco.todos(
            "SELECT id, numero, status, total_centavos, validade FROM orcamentos WHERE contato_id=? ORDER BY criado_em DESC LIMIT 50",
            (contato_id,),
        )
        return {**self._contato_publico(contato), "conversas": historico, "orcamentos": orcamentos}

    def criar_contato(self, ator: Ator, dados: dict) -> dict:
        ator.exigir("contatos", "criar")
        return self._criar_contato(ator.empresa, dados, ator)

    def _criar_contato(self, empresa_id: str, dados: dict, ator: Ator | None = None) -> dict:
        valores = self._limpar_contato(dados)
        if valores["whatsapp"] and self.banco.um(
                "SELECT 1 AS x FROM contatos WHERE empresa_id=? AND whatsapp=?", (empresa_id, valores["whatsapp"])):
            raise ErroNegocio("Já existe um nome cadastrado com esse telefone/WhatsApp.")
        contato_id = novo_id()
        unidade = self._unidade_do_lancamento(ator) if ator is not None else None
        self.banco.executar(
            """INSERT INTO contatos(id, empresa_id, nome, telefone, whatsapp, email, tags, observacoes, status, criado_em, unidade_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (contato_id, empresa_id, valores["nome"], valores["telefone"], valores["whatsapp"], valores["email"],
             valores["tags"], valores["observacoes"], valores["status"], agora(), unidade),
        )
        self.auditar(ator, "contato.criar", contato_id, empresa_id=empresa_id)
        self._verificar_limite_nomes(empresa_id)
        self.disparar_evento(empresa_id, "nome.criado", {"id": contato_id, "nome": valores["nome"]})
        return self._contato_publico(self.banco.um("SELECT * FROM contatos WHERE id=?", (contato_id,)))

    def editar_contato(self, ator: Ator, contato_id: str, dados: dict) -> dict:
        ator.exigir("contatos", "editar")
        atual = self.obter_contato(ator, contato_id)
        valores = self._limpar_contato(dados, atual)
        if valores["whatsapp"] and self.banco.um(
                "SELECT 1 AS x FROM contatos WHERE empresa_id=? AND whatsapp=? AND id<>?", (ator.empresa, valores["whatsapp"], contato_id)):
            raise ErroNegocio("Já existe outro nome com esse telefone/WhatsApp.")
        self.banco.executar(
            "UPDATE contatos SET nome=?, telefone=?, whatsapp=?, email=?, tags=?, observacoes=?, status=? WHERE id=?",
            (valores["nome"], valores["telefone"], valores["whatsapp"], valores["email"], valores["tags"],
             valores["observacoes"], valores["status"], contato_id),
        )
        self.auditar(ator, "contato.editar", contato_id)
        return self.obter_contato(ator, contato_id)

    def anonimizar_contato(self, ator: Ator, contato_id: str) -> dict:
        """Pedido de exclusão (LGPD): apaga os dados pessoais, mas mantém o
        histórico numérico (relatórios continuam corretos)."""
        ator.exigir("contatos", "excluir")
        self.obter_contato(ator, contato_id)
        with self.banco.transacao() as c:
            c.execute(
                "UPDATE contatos SET nome='Nome removido (LGPD)', telefone=NULL, whatsapp=NULL, email=NULL, observacoes=NULL, dados='{}', tags='[]', status='inativo' WHERE id=?",
                (contato_id,),
            )
            c.execute("UPDATE mensagens SET texto='[removido a pedido do titular]', payload=NULL WHERE conversa_id IN (SELECT id FROM conversas WHERE contato_id=?)", (contato_id,))
            c.execute("UPDATE usuarios SET ativo=0 WHERE contato_id=?", (contato_id,))
        self.auditar(ator, "contato.anonimizar", contato_id)
        return self.obter_contato(ator, contato_id)

    def _tags_contato(self, contato_id: str, novas: list[str]) -> None:
        if not novas:
            return
        linha = self.banco.um("SELECT tags FROM contatos WHERE id=?", (contato_id,))
        tags = set(json.loads((linha or {}).get("tags") or "[]")) | {t[:30] for t in novas if t}
        self.banco.executar("UPDATE contatos SET tags=? WHERE id=?", (json.dumps(sorted(tags)[:15], ensure_ascii=False), contato_id))

    # ================================================================ FILAS E EQUIPE
    def listar_filas(self, ator: Ator) -> list[dict]:
        ator.exigir("filas", "ver")
        return self.banco.todos(
            """SELECT f.*,
                 (SELECT COUNT(*) FROM conversas c WHERE c.fila_id=f.id AND c.status='aguardando') AS aguardando,
                 (SELECT COUNT(*) FROM conversas c WHERE c.fila_id=f.id AND c.status='em_atendimento') AS em_atendimento,
                 (SELECT COUNT(*) FROM usuarios u WHERE u.fila_id=f.id AND u.ativo=1 AND u.perfil IN ('atendente','supervisor','admin')) AS agentes,
                 (SELECT COUNT(*) FROM usuarios u WHERE u.fila_id=f.id AND u.ativo=1 AND u.presenca='online') AS online
               FROM filas f WHERE f.empresa_id=? ORDER BY f.ativa DESC, f.nome""",
            (ator.empresa,),
        )

    def salvar_fila(self, ator: Ator, dados: dict, fila_id: str | None = None) -> dict:
        ator.exigir("filas", "editar" if fila_id else "criar")
        nome = _texto(dados.get("nome"), "nome da fila", maximo=60)
        try:
            sla = int(dados.get("sla_minutos") or 15)
        except (TypeError, ValueError):
            raise ErroNegocio("SLA inválido.") from None
        if not 1 <= sla <= 10080:
            raise ErroNegocio("O SLA precisa ficar entre 1 minuto e 7 dias.")
        ativa = 1 if dados.get("ativa", True) else 0
        if fila_id:
            if not self.banco.um("SELECT 1 AS x FROM filas WHERE id=? AND empresa_id=?", (fila_id, ator.empresa)):
                raise NaoEncontrado("Fila não encontrada.")
            self.banco.executar("UPDATE filas SET nome=?, sla_minutos=?, ativa=? WHERE id=?", (nome, sla, ativa, fila_id))
        else:
            fila_id = novo_id()
            self.banco.executar(
                "INSERT INTO filas(id, empresa_id, nome, sla_minutos, ativa, criada_em) VALUES (?,?,?,?,?,?)",
                (fila_id, ator.empresa, nome, sla, ativa, agora()),
            )
        self.auditar(ator, "fila.salvar", fila_id, {"nome": nome, "sla": sla})
        return next(f for f in self.listar_filas(ator) if f["id"] == fila_id)

    def equipe(self, ator: Ator) -> list[dict]:
        ator.exigir("filas", "ver")
        linhas = self.banco.todos(
            """SELECT u.id, u.nome, u.perfil, u.presenca, u.fila_id, f.nome AS fila_nome,
                 (SELECT COUNT(*) FROM conversas c WHERE c.responsavel_id=u.id AND c.status='em_atendimento') AS em_atendimento
               FROM usuarios u LEFT JOIN filas f ON f.id=u.fila_id
               WHERE u.empresa_id=? AND u.ativo=1 AND u.perfil IN ('admin','supervisor','atendente')
               ORDER BY CASE u.presenca WHEN 'online' THEN 0 WHEN 'ausente' THEN 1 ELSE 2 END, u.nome""",
            (ator.empresa,),
        )
        return [u for u in linhas if self._usuario_no_alcance(ator, u["id"])]

    def _fila_padrao(self, empresa_id: str) -> dict | None:
        return self.banco.um("SELECT * FROM filas WHERE empresa_id=? AND ativa=1 ORDER BY criada_em LIMIT 1", (empresa_id,))

    # ================================================================ CONVERSAS
    def _conversa(self, empresa_id: str, conversa_id: str) -> dict:
        conversa = self.banco.um("SELECT * FROM conversas WHERE id=? AND empresa_id=?", (conversa_id, empresa_id))
        if not conversa:
            raise NaoEncontrado("Atendimento não encontrado.")
        return conversa

    def _pode_ver_conversa(self, ator: Ator, conversa: dict) -> bool:
        # RMD Atendimento Church: quem é lotado numa igreja/setor/campo só vê as conversas dessa parte
        filtro_igreja = getattr(self, "_conversa_no_escopo_igreja", None)
        if filtro_igreja and ator.perfil != "cliente" and not filtro_igreja(ator, conversa):
            return False
        if ator.perfil in ("owner", "admin", "supervisor"):
            return True
        if ator.perfil == "atendente":
            return (conversa["responsavel_id"] in (None, ator.usuario_id)
                    and (not ator.fila_id or conversa["fila_id"] in (None, ator.fila_id) or conversa["responsavel_id"] == ator.usuario_id))
        if ator.perfil == "cliente":
            return conversa["contato_id"] == ator.contato_id
        return False

    def listar_conversas(self, ator: Ator, status: str = "", busca: str = "", minhas: bool = False, limite: int = 100) -> list[dict]:
        ator.exigir("conversas", "ver")
        sql = """SELECT c.*, ct.nome AS contato_nome, ct.whatsapp AS contato_whatsapp, f.nome AS fila_nome, u.nome AS responsavel_nome,
                    (SELECT texto FROM mensagens m WHERE m.conversa_id=c.id ORDER BY m.criada_em DESC, m.rowid DESC LIMIT 1) AS ultima_mensagem
                 FROM conversas c JOIN contatos ct ON ct.id=c.contato_id
                 LEFT JOIN filas f ON f.id=c.fila_id LEFT JOIN usuarios u ON u.id=c.responsavel_id
                 WHERE c.empresa_id=?"""
        parametros: list = [ator.empresa]
        if status == "abertas":
            sql += " AND c.status IN ('novo','robo','aguardando','em_atendimento')"
        elif status:
            if status not in STATUS_CONVERSA:
                raise ErroNegocio("Status inválido.")
            sql += " AND c.status=?"
            parametros.append(status)
        if busca:
            sql += " AND (ct.nome LIKE ? OR CAST(c.numero AS TEXT) LIKE ?)"
            parametros += [f"%{busca}%", f"%{busca}%"]
        if minhas:
            sql += " AND c.responsavel_id=?"
            parametros.append(ator.usuario_id)
        sql += " ORDER BY c.atualizada_em DESC LIMIT ?"
        parametros.append(max(1, min(limite, 500)))
        linhas = [c for c in self.banco.todos(sql, parametros) if self._pode_ver_conversa(ator, c)]
        for c in linhas:
            c["prioridade"], c["sla_restante"] = prioridade_sla(c["sla_vence_em"], c["criada_em"]) if not c["primeira_resposta_em"] and c["status"] in ("aguardando", "novo", "robo") else ("normal", None)
            c.pop("token_publico", None)
            c.pop("fluxo_estado", None)
        return linhas

    def obter_conversa(self, ator: Ator, conversa_id: str) -> dict:
        ator.exigir("conversas", "ver")
        conversa = self._conversa(ator.empresa, conversa_id)
        if not self._pode_ver_conversa(ator, conversa):
            raise NaoEncontrado("Atendimento não encontrado.")
        return self._conversa_completa(conversa)

    def _conversa_completa(self, conversa: dict) -> dict:
        contato = self.banco.um("SELECT * FROM contatos WHERE id=?", (conversa["contato_id"],))
        mensagens = self.banco.todos("SELECT * FROM mensagens WHERE conversa_id=? ORDER BY criada_em, rowid", (conversa["id"],))
        for m in mensagens:
            m["payload"] = json.loads(m["payload"]) if m["payload"] else None
        extra = self.banco.um(
            "SELECT f.nome AS fila_nome, u.nome AS responsavel_nome FROM conversas c LEFT JOIN filas f ON f.id=c.fila_id LEFT JOIN usuarios u ON u.id=c.responsavel_id WHERE c.id=?",
            (conversa["id"],),
        ) or {}
        resultado = {k: v for k, v in conversa.items() if k not in ("token_publico", "fluxo_estado")}
        estado = json.loads(conversa["fluxo_estado"]) if conversa.get("fluxo_estado") else None
        resultado.update(extra)
        resultado["contato"] = self._contato_publico(contato) if contato else None
        resultado["mensagens"] = mensagens
        resultado["memoria_robo"] = (estado or {}).get("vars", {})
        return resultado

    def _nova_conversa(self, empresa_id: str, contato_id: str, canal: str, canal_id: str | None = None,
                       fila_id: str | None = None, publico: bool = False) -> dict:
        fila = (self.banco.um("SELECT * FROM filas WHERE id=? AND empresa_id=?", (fila_id, empresa_id)) if fila_id else None) or self._fila_padrao(empresa_id)
        conversa_id = novo_id()
        agora_txt = agora()
        with self.banco.transacao() as c:
            numero = self.banco.proximo_numero(c, empresa_id, "conversa", 10001)
            c.execute(
                """INSERT INTO conversas(id, empresa_id, numero, contato_id, canal, canal_id, status, fila_id, sla_vence_em,
                   token_publico, criada_em, atualizada_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (conversa_id, empresa_id, numero, contato_id, canal, canal_id, "novo", fila["id"] if fila else None,
                 somar_minutos(agora_txt, fila["sla_minutos"]) if fila else None,
                 secrets.token_urlsafe(24) if publico else None, agora_txt, agora_txt),
            )
            c.execute("UPDATE contatos SET ultimo_contato=?, status=CASE WHEN status='inativo' THEN 'ativo' ELSE status END WHERE id=?", (agora_txt, contato_id))
        self.disparar_evento(empresa_id, "atendimento.criado", {"id": conversa_id, "numero": numero, "canal": canal})
        return self._conversa(empresa_id, conversa_id)

    def _gravar_mensagem(self, conversa: dict, direcao: str, autor_tipo: str, texto: str, autor_id: str | None = None,
                         tipo: str = "texto", payload=None, externo_id: str | None = None, status_entrega: str | None = None) -> dict:
        mensagem_id = novo_id()
        agora_txt = agora()
        self.banco.executar(
            """INSERT INTO mensagens(id, empresa_id, conversa_id, direcao, autor_tipo, autor_id, texto, tipo, payload, externo_id,
               status_entrega, criada_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mensagem_id, conversa["empresa_id"], conversa["id"], direcao, autor_tipo, autor_id, (texto or "")[:4000], tipo,
             json.dumps(payload, ensure_ascii=False) if payload is not None else None, externo_id, status_entrega, agora_txt),
        )
        self.banco.executar("UPDATE conversas SET atualizada_em=? WHERE id=?", (agora_txt, conversa["id"]))
        return self.banco.um("SELECT * FROM mensagens WHERE id=?", (mensagem_id,))

    def _saida_do_robo(self, conversa: dict, saida: dict) -> None:
        opcoes = saida.get("opcoes") or []
        texto = saida["texto"]
        mensagem = self._gravar_mensagem(conversa, "saida", "robo", texto, tipo="interativo" if opcoes else "texto",
                                         payload={"opcoes": opcoes} if opcoes else None)
        self._entregar(conversa, mensagem, texto, opcoes)

    def _colocar_na_fila(self, conversa: dict, fila_id: str | None) -> dict:
        fila = (self.banco.um("SELECT * FROM filas WHERE id=? AND empresa_id=?", (fila_id, conversa["empresa_id"])) if fila_id else None) \
            or self._fila_padrao(conversa["empresa_id"])
        sla = somar_minutos(agora(), fila["sla_minutos"]) if fila and not conversa["primeira_resposta_em"] else conversa["sla_vence_em"]
        responsavel = None
        config = self.banco.um("SELECT atribuicao_automatica FROM config_empresa WHERE empresa_id=?", (conversa["empresa_id"],)) or {}
        if config.get("atribuicao_automatica") and fila:
            livre = self.banco.um(
                """SELECT u.id FROM usuarios u WHERE u.empresa_id=? AND u.fila_id=? AND u.ativo=1 AND u.presenca='online'
                     AND u.perfil IN ('atendente','supervisor')
                   ORDER BY (SELECT COUNT(*) FROM conversas c WHERE c.responsavel_id=u.id AND c.status='em_atendimento'), u.nome LIMIT 1""",
                (conversa["empresa_id"], fila["id"]),
            )
            responsavel = livre["id"] if livre else None
        self.banco.executar(
            "UPDATE conversas SET status=?, fila_id=?, sla_vence_em=?, responsavel_id=COALESCE(?, responsavel_id), atualizada_em=? WHERE id=?",
            ("em_atendimento" if responsavel else "aguardando", fila["id"] if fila else None, sla, responsavel, agora(), conversa["id"]),
        )
        return self._conversa(conversa["empresa_id"], conversa["id"])

    def _rodar_robo(self, conversa: dict, entrada: str | None) -> dict:
        """Roda o fluxo publicado. Devolve a conversa atualizada."""
        estado = json.loads(conversa["fluxo_estado"]) if conversa.get("fluxo_estado") else None
        if estado is None:
            fluxo = self._fluxo_para_iniciar(conversa["empresa_id"], entrada)
            if not fluxo:
                return self._colocar_na_fila(conversa, None)
            estado = {"fluxo_id": fluxo["id"], "passo": 0, "vars": {}}
            entrada_para_motor = None
        else:
            fluxo = self.banco.um("SELECT * FROM fluxos WHERE id=?", (estado.get("fluxo_id"),))
            entrada_para_motor = entrada
            if not fluxo:
                return self._colocar_na_fila(conversa, None)
        contato = self.banco.um("SELECT nome FROM contatos WHERE id=?", (conversa["contato_id"],)) or {}
        config = self.obter_config(conversa["empresa_id"])
        contexto = {"nome": (contato.get("nome") or "").split(" ")[0], "empresa": config["empresa_nome"]}
        resultado = motor.avancar(json.loads(fluxo["etapas"]), estado, entrada_para_motor, contexto)
        for saida in resultado.saidas:
            self._saida_do_robo(conversa, saida)
        self._tags_contato(conversa["contato_id"], resultado.tags)
        memoria = resultado.estado.get("vars", {})
        self.banco.executar(
            "UPDATE contatos SET dados=json_patch(COALESCE(dados,'{}'), ?) WHERE id=?",
            (json.dumps({k: v for k, v in memoria.items() if k not in ("nome", "empresa")}, ensure_ascii=False), conversa["contato_id"]),
        )
        if resultado.acao is None:
            self.banco.executar("UPDATE conversas SET status='robo', fluxo_estado=?, atualizada_em=? WHERE id=?",
                                (json.dumps(resultado.estado, ensure_ascii=False), agora(), conversa["id"]))
            return self._conversa(conversa["empresa_id"], conversa["id"])
        self.banco.executar("UPDATE conversas SET fluxo_estado=? WHERE id=?", (json.dumps(resultado.estado, ensure_ascii=False), conversa["id"]))
        conversa = self._conversa(conversa["empresa_id"], conversa["id"])
        if resultado.acao == "encerrar":
            return self._finalizar(conversa, None, pedir_avaliacao=False)
        return self._colocar_na_fila(conversa, resultado.fila_id)

    def receber_mensagem(self, empresa_id: str, contato_id: str, canal: str, texto: str, canal_id: str | None = None,
                         externo_id: str | None = None, payload=None) -> dict:
        """Mensagem que chegou do cliente (WhatsApp, chat do site ou portal)."""
        conversa = self.banco.um(
            """SELECT * FROM conversas WHERE empresa_id=? AND contato_id=? AND canal=? AND status<>'resolvido'
               ORDER BY criada_em DESC LIMIT 1""",
            (empresa_id, contato_id, canal),
        )
        nova = conversa is None
        if nova:
            conversa = self._nova_conversa(empresa_id, contato_id, canal, canal_id)
        self._gravar_mensagem(conversa, "entrada", "contato", texto, autor_id=contato_id, payload=payload, externo_id=externo_id)
        self.banco.executar("UPDATE contatos SET ultimo_contato=? WHERE id=?", (agora(), contato_id))
        self.disparar_evento(empresa_id, "mensagem.recebida", {"atendimento_id": conversa["id"], "texto": texto})
        if nova:
            config = self.obter_config(empresa_id)
            conversa = self._conversa(empresa_id, conversa["id"])
            if not self._fluxo_para_iniciar(empresa_id, texto) and config.get("mensagem_inicial"):
                self._saida_do_robo(conversa, {"texto": config["mensagem_inicial"], "opcoes": []})
            return self._rodar_robo(conversa, texto)
        if conversa["status"] == "robo":
            return self._rodar_robo(conversa, texto)
        return self._conversa(empresa_id, conversa["id"])

    def _exigir_conversa_visivel(self, ator: Ator, conversa_id: str) -> dict:
        conversa = self._conversa(ator.empresa, conversa_id)
        if not self._pode_ver_conversa(ator, conversa):
            raise NaoEncontrado("Atendimento não encontrado.")
        return conversa

    def responder(self, ator: Ator, conversa_id: str, texto: str) -> dict:
        ator.exigir("conversas", "responder")
        texto = _texto(texto, "mensagem", maximo=4000)
        conversa = self._exigir_conversa_visivel(ator, conversa_id)
        if conversa["status"] == "resolvido":
            raise ErroNegocio("Este atendimento já foi resolvido. Abra um novo.")
        mensagem = self._gravar_mensagem(conversa, "saida", "usuario", texto, autor_id=ator.usuario_id)
        self.banco.executar(
            """UPDATE conversas SET status='em_atendimento', responsavel_id=COALESCE(responsavel_id, ?),
               primeira_resposta_em=COALESCE(primeira_resposta_em, ?), fluxo_estado=NULL, atualizada_em=? WHERE id=?""",
            (ator.usuario_id, agora(), agora(), conversa_id),
        )
        self._entregar(self._conversa(ator.empresa, conversa_id), mensagem, texto, [])
        return self.obter_conversa(ator, conversa_id)

    def assumir(self, ator: Ator, conversa_id: str) -> dict:
        ator.exigir("conversas", "responder")
        conversa = self._exigir_conversa_visivel(ator, conversa_id)
        if conversa["responsavel_id"] and conversa["responsavel_id"] != ator.usuario_id and not ator.pode("conversas", "atribuir"):
            raise ErroNegocio("Este atendimento já tem responsável.")
        self.banco.executar(
            "UPDATE conversas SET responsavel_id=?, status=CASE WHEN status='resolvido' THEN status ELSE 'em_atendimento' END, fluxo_estado=NULL, atualizada_em=? WHERE id=?",
            (ator.usuario_id, agora(), conversa_id),
        )
        self.auditar(ator, "atendimento.assumir", conversa_id)
        return self.obter_conversa(ator, conversa_id)

    def transferir(self, ator: Ator, conversa_id: str, fila_id: str | None = None, responsavel_id: str | None = None) -> dict:
        ator.exigir("conversas", "responder")
        conversa = self._exigir_conversa_visivel(ator, conversa_id)
        if responsavel_id:
            destino = self.banco.um("SELECT id, fila_id FROM usuarios WHERE id=? AND empresa_id=? AND ativo=1 AND perfil<>'cliente'",
                                    (responsavel_id, ator.empresa))
            if not destino:
                raise ErroNegocio("Atendente inválido.")
            fila_id = fila_id or destino["fila_id"] or conversa["fila_id"]
        if fila_id and not self.banco.um("SELECT 1 AS x FROM filas WHERE id=? AND empresa_id=?", (fila_id, ator.empresa)):
            raise ErroNegocio("Fila inválida.")
        if not fila_id and not responsavel_id:
            raise ErroNegocio("Escolha a fila ou o atendente de destino.")
        self.banco.executar(
            "UPDATE conversas SET fila_id=COALESCE(?, fila_id), responsavel_id=?, status=?, fluxo_estado=NULL, atualizada_em=? WHERE id=?",
            (fila_id, responsavel_id, "em_atendimento" if responsavel_id else "aguardando", agora(), conversa_id),
        )
        self._gravar_mensagem(conversa, "sistema", "sistema", f"Atendimento transferido por {ator.nome}.")
        self.auditar(ator, "atendimento.transferir", conversa_id, {"fila": fila_id, "responsavel": responsavel_id})
        conversa = self._conversa(ator.empresa, conversa_id)
        return self._conversa_completa(conversa)

    def resolver(self, ator: Ator, conversa_id: str) -> dict:
        ator.exigir("conversas", "encerrar")
        conversa = self._exigir_conversa_visivel(ator, conversa_id)
        if conversa["status"] == "resolvido":
            return self.obter_conversa(ator, conversa_id)
        self._finalizar(conversa, ator)
        self.auditar(ator, "atendimento.resolver", conversa_id)
        return self._conversa_completa(self._conversa(ator.empresa, conversa_id))

    def _finalizar(self, conversa: dict, ator: Ator | None, pedir_avaliacao: bool = True) -> dict:
        self.banco.executar(
            "UPDATE conversas SET status='resolvido', resolvida_em=?, fluxo_estado=NULL, atualizada_em=? WHERE id=?",
            (agora(), agora(), conversa["id"]),
        )
        config = self.banco.um("SELECT pedir_avaliacao FROM config_empresa WHERE empresa_id=?", (conversa["empresa_id"],)) or {}
        if pedir_avaliacao and config.get("pedir_avaliacao") and conversa["canal"] in ("web", "whatsapp", "portal"):
            self._saida_do_robo(conversa, {
                "texto": "Atendimento finalizado. Como você avalia o nosso atendimento? Responda de 1 (ruim) a 5 (ótimo).",
                "opcoes": ["1", "2", "3", "4", "5"],
            })
        self.disparar_evento(conversa["empresa_id"], "atendimento.resolvido", {"id": conversa["id"], "numero": conversa["numero"]})
        return self._conversa(conversa["empresa_id"], conversa["id"])

    def registrar_avaliacao(self, empresa_id: str, conversa_id: str, nota) -> bool:
        try:
            nota = int(str(nota).strip())
        except (TypeError, ValueError):
            return False
        if not 1 <= nota <= 5:
            return False
        alterou = self.banco.executar(
            "UPDATE conversas SET avaliacao=? WHERE id=? AND empresa_id=? AND status='resolvido' AND avaliacao IS NULL",
            (nota, conversa_id, empresa_id),
        )
        return bool(alterou)

    def iniciar_conversa_ativa(self, ator: Ator, contato_id: str, texto: str) -> dict:
        """A empresa inicia a conversa (ex.: retorno a um cliente)."""
        ator.exigir("conversas", "responder")
        contato = self.obter_contato(ator, contato_id)
        canal = "whatsapp" if contato["whatsapp"] and self._canal_whatsapp_ativo(ator.empresa) else "interno"
        conversa = self._nova_conversa(ator.empresa, contato_id, canal, fila_id=ator.fila_id)
        self.banco.executar("UPDATE conversas SET status='em_atendimento', responsavel_id=? WHERE id=?", (ator.usuario_id, conversa["id"]))
        return self.responder(ator, conversa["id"], texto)

    # ================================================================ CHAT DO SITE (público)
    def publico_iniciar(self, slug: str, nome: str, telefone: str | None = None, email: str | None = None, texto: str | None = None) -> dict:
        empresa = self.empresa_por_slug(slug)
        if not empresa:
            raise NaoEncontrado("Empresa não encontrada.")
        nome = _texto(nome, "seu nome", maximo=120)
        whatsapp = normalizar_telefone(telefone)
        contato = self.banco.um("SELECT * FROM contatos WHERE empresa_id=? AND whatsapp=?", (empresa["id"], whatsapp)) if whatsapp else None
        if not contato:
            contato = self._criar_contato(empresa["id"], {"nome": nome, "telefone": telefone, "email": email, "tags": ["site"]})
        conversa = self._nova_conversa(empresa["id"], contato["id"], "web", publico=True)
        config = self.obter_config(empresa["id"])
        primeiro = texto or ""
        if primeiro:
            self._gravar_mensagem(conversa, "entrada", "contato", primeiro, autor_id=contato["id"])
        if not self._fluxo_para_iniciar(empresa["id"], primeiro) and config.get("mensagem_inicial"):
            self._saida_do_robo(conversa, {"texto": config["mensagem_inicial"], "opcoes": []})
        self._rodar_robo(self._conversa(empresa["id"], conversa["id"]), primeiro or None)
        conversa = self._conversa(empresa["id"], conversa["id"])
        return {"token": conversa["token_publico"], **self.publico_estado(conversa["token_publico"])}

    def _conversa_por_token(self, token: str) -> dict:
        if not token or len(token) < 20:
            raise NaoEncontrado("Conversa não encontrada.")
        conversa = self.banco.um("SELECT * FROM conversas WHERE token_publico=?", (token,))
        if not conversa:
            raise NaoEncontrado("Conversa não encontrada.")
        return conversa

    def publico_estado(self, token: str, depois_de: str | None = None) -> dict:
        conversa = self._conversa_por_token(token)
        sql = "SELECT id, direcao, autor_tipo, texto, tipo, payload, criada_em FROM mensagens WHERE conversa_id=? AND direcao<>'sistema'"
        parametros: list = [conversa["id"]]
        if depois_de:
            sql += " AND criada_em >= ?"
            parametros.append(depois_de)
        mensagens = self.banco.todos(sql + " ORDER BY criada_em, rowid", parametros)
        for m in mensagens:
            m["payload"] = json.loads(m["payload"]) if m["payload"] else None
        config = self.obter_config(conversa["empresa_id"])
        return {
            "numero": conversa["numero"], "status": conversa["status"], "avaliacao": conversa["avaliacao"],
            "empresa": {"nome": config["empresa_nome"], "logo": config.get("logo"), "tema": config["tema"],
                        "cor_destaque": config.get("cor_destaque"), "nome_sistema": config["nome_sistema"]},
            "mensagens": mensagens,
        }

    def publico_enviar(self, token: str, texto: str) -> dict:
        conversa = self._conversa_por_token(token)
        texto = _texto(texto, "mensagem", maximo=2000)
        if conversa["status"] == "resolvido":
            if conversa["avaliacao"] is None and self.registrar_avaliacao(conversa["empresa_id"], conversa["id"], texto):
                self._gravar_mensagem(conversa, "entrada", "contato", texto, autor_id=conversa["contato_id"])
                self._saida_do_robo(conversa, {"texto": "Obrigado pela avaliação!", "opcoes": []})
                return self.publico_estado(token)
            raise ErroNegocio("Este atendimento foi encerrado. Recarregue a página para começar outro.")
        self._gravar_mensagem(conversa, "entrada", "contato", texto, autor_id=conversa["contato_id"])
        self.disparar_evento(conversa["empresa_id"], "mensagem.recebida", {"atendimento_id": conversa["id"], "texto": texto})
        if conversa["status"] == "robo":
            self._rodar_robo(conversa, texto)
        return self.publico_estado(token)

    # ================================================================ PORTAL DO CLIENTE
    def portal_resumo(self, ator: Ator) -> dict:
        ator.exigir("portal", "ver")
        if not ator.contato_id:
            raise ErroNegocio("Seu usuário não está ligado a um cadastro.")
        contato = self.banco.um("SELECT * FROM contatos WHERE id=? AND empresa_id=?", (ator.contato_id, ator.empresa))
        conversas = self.banco.todos(
            "SELECT id, numero, canal, status, criada_em, resolvida_em, avaliacao FROM conversas WHERE contato_id=? ORDER BY criada_em DESC",
            (ator.contato_id,),
        )
        orcamentos = self.banco.todos(
            "SELECT id, numero, descricao, status, total_centavos, validade, enviado_em FROM orcamentos WHERE contato_id=? AND status<>'rascunho' ORDER BY criado_em DESC",
            (ator.contato_id,),
        )
        agenda = self.banco.todos(
            "SELECT id, titulo, inicio, fim, status, observacao FROM agenda WHERE contato_id=? AND status<>'cancelado' ORDER BY inicio",
            (ator.contato_id,),
        )
        return {"contato": self._contato_publico(contato) if contato else None, "conversas": conversas,
                "orcamentos": [self._atualizar_vencimento(o) for o in orcamentos], "agenda": agenda}

    def portal_conversa(self, ator: Ator, conversa_id: str) -> dict:
        ator.exigir("portal", "ver")
        conversa = self._conversa(ator.empresa, conversa_id)
        if conversa["contato_id"] != ator.contato_id:
            raise NaoEncontrado("Atendimento não encontrado.")
        dados = self._conversa_completa(conversa)
        dados["mensagens"] = [m for m in dados["mensagens"] if m["direcao"] != "sistema"]
        dados.pop("memoria_robo", None)
        return dados

    def portal_enviar(self, ator: Ator, texto: str) -> dict:
        ator.exigir("portal", "mensagem")
        texto = _texto(texto, "mensagem", maximo=2000)
        conversa = self.banco.um(
            "SELECT * FROM conversas WHERE contato_id=? AND canal='portal' AND status='resolvido' AND avaliacao IS NULL ORDER BY resolvida_em DESC LIMIT 1",
            (ator.contato_id,),
        )
        aberta = self.banco.um(
            "SELECT id FROM conversas WHERE contato_id=? AND canal='portal' AND status<>'resolvido' LIMIT 1", (ator.contato_id,))
        if conversa and not aberta and self.registrar_avaliacao(ator.empresa, conversa["id"], texto):
            self._gravar_mensagem(conversa, "entrada", "contato", texto, autor_id=ator.contato_id)
            return self.portal_conversa(ator, conversa["id"])
        resultado = self.receber_mensagem(ator.empresa, ator.contato_id, "portal", texto)
        return self.portal_conversa(ator, resultado["id"])
