"""Dashboard, alertas, relatórios, backup e plano & limites."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .db import agora, para_datahora, pasta_dados
from .nucleo import Ator, ErroNegocio, NaoEncontrado, novo_id

NIVEIS_ALERTA = ("urgente", "atencao", "info")
FORMATO_BACKUP = "rmd-atendimento-backup"
# Ordem respeita as ligações entre tabelas. Segredos (tokens do WhatsApp,
# chaves de API, sessões) nunca entram no backup.
TABELAS_BACKUP = (
    "filas", "contatos", "usuarios", "servicos", "conversas", "mensagens", "orcamentos", "orcamento_itens",
    "fluxos", "agenda", "alertas", "igreja_unidades", "igreja_lotacoes", "igreja_jornada", "igreja_oracoes",
)
CHAVES_PRIMARIAS = {t: "id" for t in TABELAS_BACKUP}
MANTER_BACKUPS_AUTOMATICOS = 30


def _fuso(nome: str):
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(nome)
    except Exception:  # noqa: BLE001 - sem base de fusos: usa UTC-3 (Brasil)
        return timezone(timedelta(hours=-3))


def _minutos_segundos(segundos: float | None) -> str:
    if segundos is None:
        return "—"
    segundos = int(round(segundos))
    return f"{segundos // 60:02d}:{segundos % 60:02d}"


class GestaoMixin:
    # ================================================================ ALERTAS
    def _novo_alerta(self, empresa_id: str, chave: str, tipo: str, nivel: str, titulo: str, texto: str,
                     referencia: str | None = None) -> None:
        self.banco.executar(
            "INSERT OR IGNORE INTO alertas(id, empresa_id, chave, tipo, nivel, titulo, texto, referencia, criado_em) VALUES (?,?,?,?,?,?,?,?,?)",
            (novo_id(), empresa_id, chave, tipo, nivel if nivel in NIVEIS_ALERTA else "info", titulo[:120], texto[:500], referencia, agora()),
        )

    def gerar_alertas(self, empresa_id: str) -> None:
        agora_txt = agora()
        for conversa in self.banco.todos(
                """SELECT c.id, c.numero, ct.nome FROM conversas c JOIN contatos ct ON ct.id=c.contato_id
                   WHERE c.empresa_id=? AND c.status IN ('novo','aguardando','robo','em_atendimento') AND c.primeira_resposta_em IS NULL
                     AND c.sla_vence_em IS NOT NULL AND c.sla_vence_em < ?""", (empresa_id, agora_txt)):
            self._novo_alerta(empresa_id, f"sla:{conversa['id']}", "sla", "urgente", "SLA vencido",
                              f"Atendimento #{conversa['numero']} ({conversa['nome']}) passou do prazo de primeira resposta.", conversa["id"])
        limite = (date.today() + timedelta(days=2)).isoformat()
        for orcamento in self.banco.todos(
                """SELECT o.id, o.numero, o.validade, c.nome FROM orcamentos o JOIN contatos c ON c.id=o.contato_id
                   WHERE o.empresa_id=? AND o.status IN ('enviado','em_analise') AND o.validade <= ? AND o.validade >= ?""",
                (empresa_id, limite, date.today().isoformat())):
            self._novo_alerta(empresa_id, f"orc-vence:{orcamento['id']}", "orcamento", "info", "Orçamento perto do vencimento",
                              f"ORC-{orcamento['numero']} ({orcamento['nome']}) vence em {datetime.fromisoformat(orcamento['validade']).strftime('%d/%m')}.",
                              orcamento["id"])
        agora_dt = datetime.now(timezone.utc)
        for item in self.banco.todos(
                "SELECT a.*, c.nome AS contato_nome FROM agenda a LEFT JOIN contatos c ON c.id=a.contato_id "
                "WHERE a.empresa_id=? AND a.status IN ('agendado','confirmado','aguardando') AND a.lembrete_minutos>0 AND a.lembrete_enviado=0",
                (empresa_id,)):
            inicio = para_datahora(item["inicio"])
            if inicio and inicio - timedelta(minutes=item["lembrete_minutos"]) <= agora_dt < inicio:
                config = self.obter_config(empresa_id)
                local = inicio.astimezone(_fuso(config["fuso"])).strftime("%d/%m às %H:%M")
                self._novo_alerta(empresa_id, f"agenda:{item['id']}:{item['inicio']}", "agenda", "info", "Lembrete de agenda",
                                  f"{item['titulo']} — {item.get('contato_nome') or 'sem nome'} — {local}.", item["id"])
                self.banco.executar("UPDATE agenda SET lembrete_enviado=1 WHERE id=?", (item["id"],))
        self._verificar_limite_nomes(empresa_id)
        if hasattr(self, "gerar_alertas_igreja") and self.banco.um("SELECT 1 AS x FROM igreja_jornada WHERE empresa_id=? LIMIT 1", (empresa_id,)):
            self.gerar_alertas_igreja(empresa_id)
        ultimo = self.banco.um("SELECT MAX(criado_em) AS ultimo FROM backups WHERE empresa_id=?", (empresa_id,))
        ultimo_dt = para_datahora((ultimo or {}).get("ultimo"))
        if ultimo_dt is None or agora_dt - ultimo_dt > timedelta(days=7):
            semana = date.today().isocalendar()
            self._novo_alerta(empresa_id, f"backup:{semana[0]}-{semana[1]}", "backup", "atencao", "Backup atrasado",
                              "Nenhum backup nos últimos 7 dias. Crie um em Administração > Backup.")

    def listar_alertas(self, ator: Ator, somente_nao_lidos: bool = False) -> dict:
        ator.exigir("alertas", "ver")
        self.gerar_alertas(ator.empresa)
        sql = "SELECT * FROM alertas WHERE empresa_id=?" + (" AND lido=0" if somente_nao_lidos else "")
        itens = self.banco.todos(sql + " ORDER BY lido, CASE nivel WHEN 'urgente' THEN 0 WHEN 'atencao' THEN 1 ELSE 2 END, criado_em DESC LIMIT 200",
                                 (ator.empresa,))
        filtro_igreja = getattr(self, "_filtrar_alertas_igreja", None)
        if filtro_igreja:
            itens = filtro_igreja(ator, itens)
        return {"itens": itens, "nao_lidos": self.contar_alertas(ator.empresa, ator)}

    def contar_alertas(self, empresa_id: str, ator: Ator | None = None) -> int:
        filtro_igreja = getattr(self, "_filtrar_alertas_igreja", None)
        if ator is not None and filtro_igreja:
            return len(filtro_igreja(ator, self.banco.todos("SELECT * FROM alertas WHERE empresa_id=? AND lido=0", (empresa_id,))))
        return (self.banco.um("SELECT COUNT(*) AS n FROM alertas WHERE empresa_id=? AND lido=0", (empresa_id,)) or {}).get("n", 0)

    def marcar_alertas(self, ator: Ator, alerta_id: str | None = None) -> int:
        ator.exigir("alertas", "marcar")
        filtro_igreja = getattr(self, "_filtrar_alertas_igreja", None)
        visiveis = None
        if filtro_igreja:
            todos = self.banco.todos("SELECT * FROM alertas WHERE empresa_id=? AND lido=0", (ator.empresa,))
            meus = filtro_igreja(ator, todos)
            if len(meus) != len(todos):  # lotado numa parte: só marca os alertas que ele enxerga
                visiveis = {a["id"] for a in meus}
        if alerta_id:
            if visiveis is not None and alerta_id not in visiveis:
                return 0
            return self.banco.executar("UPDATE alertas SET lido=1 WHERE id=? AND empresa_id=?", (alerta_id, ator.empresa))
        if visiveis is not None:
            for i in visiveis:
                self.banco.executar("UPDATE alertas SET lido=1 WHERE id=? AND empresa_id=?", (i, ator.empresa))
            return len(visiveis)
        return self.banco.executar("UPDATE alertas SET lido=1 WHERE empresa_id=? AND lido=0", (ator.empresa,))

    # ================================================================ PLANO & LIMITES
    def uso_do_plano(self, empresa_id: str) -> dict:
        empresa = self.obter_empresa(empresa_id)
        plano = self.banco.um("SELECT * FROM planos WHERE codigo=?", (empresa["plano"],))
        nomes = self.banco.um("SELECT COUNT(*) AS n FROM contatos WHERE empresa_id=?", (empresa_id,))["n"]
        canais = self.banco.um("SELECT COUNT(*) AS n FROM whatsapp_canais WHERE empresa_id=? AND ativo=1", (empresa_id,))["n"]
        usuarios = self.banco.um("SELECT COUNT(*) AS n FROM usuarios WHERE empresa_id=? AND ativo=1 AND perfil<>'cliente'", (empresa_id,))["n"]

        def item(usado, limite):
            return {"usado": usado, "limite": limite, "percentual": round(100 * usado / limite) if limite else 0}

        return {
            "plano": plano, "modo": "alerta",
            "nomes": item(nomes, plano["limite_nomes"]),
            "canais_whatsapp": item(canais, plano["limite_canais_whatsapp"]),
            "usuarios": item(usuarios, plano["limite_usuarios"]),
            "planos": self.banco.todos("SELECT * FROM planos ORDER BY limite_nomes"),
        }

    def plano(self, ator: Ator) -> dict:
        ator.exigir("plano", "ver")
        return self.uso_do_plano(ator.empresa)

    def _alerta_limite(self, empresa_id: str, recurso: str, nome: str) -> None:
        uso = self.uso_do_plano(empresa_id)[recurso]
        mes = date.today().strftime("%Y-%m")
        if uso["percentual"] >= 100:
            self._novo_alerta(empresa_id, f"quota-{recurso}-100:{mes}", "quota", "urgente", "Limite do plano atingido",
                              f"{nome}: {uso['usado']} de {uso['limite']} ({uso['percentual']}%). O sistema continua funcionando, mas é hora de mudar de plano.")
        elif uso["percentual"] >= 80:
            self._novo_alerta(empresa_id, f"quota-{recurso}-80:{mes}", "quota", "info", "Plano perto do limite",
                              f"{nome}: {uso['usado']} de {uso['limite']} ({uso['percentual']}%).")

    def _verificar_limite_nomes(self, empresa_id: str) -> None:
        self._alerta_limite(empresa_id, "nomes", "Uso de nomes")

    def _verificar_limite_canais(self, empresa_id: str) -> None:
        self._alerta_limite(empresa_id, "canais_whatsapp", "Canais de WhatsApp")

    # ================================================================ PERÍODOS
    def _inicio_periodo(self, empresa_id: str, dias: int) -> str:
        config = self.obter_config(empresa_id)
        fuso = _fuso(config["fuso"])
        hoje_local = datetime.now(fuso).replace(hour=0, minute=0, second=0, microsecond=0)
        return (hoje_local - timedelta(days=max(0, dias - 1))).astimezone(timezone.utc).isoformat(timespec="seconds")

    # ================================================================ DASHBOARD
    def dashboard(self, ator: Ator) -> dict:
        ator.exigir("dashboard", "ver")
        empresa_id = ator.empresa
        self.gerar_alertas(empresa_id)
        hoje = self._inicio_periodo(empresa_id, 1)
        ontem = self._inicio_periodo(empresa_id, 2)
        fc, pc = self._filtro_conversas_alcance(ator, "id")  # parte da igreja: só os números da sua parte

        def contar(sql, p):
            return (self.banco.um(sql + fc, (*p, *pc)) or {}).get("n") or 0
        hoje_n = contar("SELECT COUNT(*) AS n FROM conversas WHERE empresa_id=? AND criada_em>=?", (empresa_id, hoje))
        ontem_n = contar("SELECT COUNT(*) AS n FROM conversas WHERE empresa_id=? AND criada_em>=? AND criada_em<?", (empresa_id, ontem, hoje))
        em_atendimento = contar("SELECT COUNT(*) AS n FROM conversas WHERE empresa_id=? AND status='em_atendimento'", (empresa_id,))
        aguardando = contar("SELECT COUNT(*) AS n FROM conversas WHERE empresa_id=? AND status IN ('aguardando','novo')", (empresa_id,))
        no_robo = contar("SELECT COUNT(*) AS n FROM conversas WHERE empresa_id=? AND status='robo'", (empresa_id,))

        def sla(inicio, fim=None):
            sql = "SELECT COUNT(*) AS total, SUM(CASE WHEN primeira_resposta_em<=sla_vence_em THEN 1 ELSE 0 END) AS ok FROM conversas WHERE empresa_id=? AND primeira_resposta_em>=? AND sla_vence_em IS NOT NULL"
            parametros = [empresa_id, inicio]
            if fim:
                sql += " AND primeira_resposta_em<?"
                parametros.append(fim)
            linha = self.banco.um(sql + fc, (*parametros, *pc)) or {}
            return round(100 * (linha.get("ok") or 0) / linha["total"]) if linha.get("total") else None

        sla_7 = sla(self._inicio_periodo(empresa_id, 7))
        sla_ant = sla(self._inicio_periodo(empresa_id, 14), self._inicio_periodo(empresa_id, 7))
        limite = (date.today() + timedelta(days=2)).isoformat()
        if fc:
            abertos = [o for o in self.banco.todos(
                "SELECT * FROM orcamentos WHERE empresa_id=? AND status IN ('enviado','em_analise') AND validade>=?",
                (empresa_id, date.today().isoformat())) if self._orcamento_no_alcance(ator, o)]
            orc = {"abertos": len(abertos), "vencendo": sum(1 for o in abertos if o["validade"] <= limite)}
        else:
            orc = self.banco.um(
                "SELECT COUNT(*) AS abertos, SUM(CASE WHEN validade<=? THEN 1 ELSE 0 END) AS vencendo FROM orcamentos WHERE empresa_id=? AND status IN ('enviado','em_analise') AND validade>=?",
                (limite, empresa_id, date.today().isoformat()),
            ) or {}

        def csat(inicio, fim=None):
            sql = "SELECT AVG(avaliacao) AS m, COUNT(avaliacao) AS n FROM conversas WHERE empresa_id=? AND avaliacao IS NOT NULL AND resolvida_em>=?"
            parametros = [empresa_id, inicio]
            if fim:
                sql += " AND resolvida_em<?"
                parametros.append(fim)
            linha = self.banco.um(sql + fc, (*parametros, *pc)) or {}
            return round(linha["m"], 1) if linha.get("n") else None

        csat_30 = csat(self._inicio_periodo(empresa_id, 30))
        csat_ant = csat(self._inicio_periodo(empresa_id, 60), self._inicio_periodo(empresa_id, 30))
        recentes = self.listar_conversas(ator, limite=8)
        fila = [c for c in self.listar_conversas(ator, status="abertas", limite=200)
                if not c["primeira_resposta_em"] and c["sla_vence_em"] and c["status"] in ("novo", "aguardando", "robo")]
        fila.sort(key=lambda c: c["sla_vence_em"])
        variacao = None if not ontem_n else round(100 * (hoje_n - ontem_n) / ontem_n, 1)
        return {
            "cartoes": {
                "hoje": hoje_n, "variacao_ontem": variacao,
                "em_atendimento": em_atendimento, "aguardando": aguardando, "no_robo": no_robo,
                "sla": sla_7, "sla_variacao": None if sla_7 is None or sla_ant is None else sla_7 - sla_ant,
                "orcamentos_abertos": orc.get("abertos") or 0, "orcamentos_vencendo": orc.get("vencendo") or 0,
                "csat": csat_30, "csat_variacao": None if csat_30 is None or csat_ant is None else round(csat_30 - csat_ant, 1),
            },
            "recentes": recentes, "fila_prioridade": fila[:6], "alertas_nao_lidos": self.contar_alertas(empresa_id, ator),
        }

    def _filtro_conversas_alcance(self, ator: Ator, coluna: str) -> tuple[str, list]:
        """Filtro SQL das conversas que a pessoa pode contar (vazio = Sede, vê tudo)."""
        ids = self._conversas_no_alcance(ator)
        if ids is None:
            return "", []
        if not ids:
            return " AND 1=0", []
        return f" AND {coluna} IN ({','.join('?' * len(ids))})", ids

    # ================================================================ RELATÓRIOS
    def relatorio(self, ator: Ator, dias: int = 30) -> dict:
        ator.exigir("relatorios", "ver")
        dias = dias if dias in (1, 7, 30, 90, 365) else 30
        empresa_id = ator.empresa
        inicio = self._inicio_periodo(empresa_id, dias)
        fc, pc = self._filtro_conversas_alcance(ator, "id")  # parte da igreja: relatório só da sua parte
        fcc, _ = self._filtro_conversas_alcance(ator, "c.id")
        fm, _ = self._filtro_conversas_alcance(ator, "conversa_id")
        base = self.banco.um(
            """SELECT COUNT(*) AS total,
                 SUM(CASE WHEN status='resolvido' THEN 1 ELSE 0 END) AS resolvidos,
                 AVG(CASE WHEN primeira_resposta_em IS NOT NULL THEN (julianday(primeira_resposta_em)-julianday(criada_em))*86400 END) AS primeira,
                 AVG(avaliacao) AS csat, COUNT(avaliacao) AS avaliacoes
               FROM conversas WHERE empresa_id=? AND criada_em>=?""" + fc,
            (empresa_id, inicio, *pc),
        ) or {}
        mensagens = self.banco.um("SELECT COUNT(*) AS n FROM mensagens WHERE empresa_id=? AND criada_em>=?" + fm, (empresa_id, inicio, *pc))["n"]
        if fc:
            grupos: dict = {}
            for o in self.banco.todos("SELECT * FROM orcamentos WHERE empresa_id=? AND criado_em>=?", (empresa_id, inicio)):
                if self._orcamento_no_alcance(ator, o):
                    g = grupos.setdefault(o["status"], {"status": o["status"], "quantidade": 0, "valor": 0})
                    g["quantidade"] += 1
                    g["valor"] += o["total_centavos"] or 0
            orc = list(grupos.values())
        else:
            orc = self.banco.todos(
                "SELECT status, COUNT(*) AS quantidade, SUM(total_centavos) AS valor FROM orcamentos WHERE empresa_id=? AND criado_em>=? GROUP BY status",
                (empresa_id, inicio),
            )
        decididos = {o["status"]: o["quantidade"] for o in orc}
        enviados = sum(decididos.get(s, 0) for s in ("enviado", "em_analise", "aprovado", "recusado", "vencido"))
        conversao = round(100 * decididos.get("aprovado", 0) / enviados) if enviados else None
        equipe = self.banco.todos(
            """SELECT u.nome, COUNT(c.id) AS atendimentos,
                 SUM(CASE WHEN c.status='resolvido' THEN 1 ELSE 0 END) AS resolvidos,
                 AVG(CASE WHEN c.primeira_resposta_em IS NOT NULL THEN (julianday(c.primeira_resposta_em)-julianday(c.criada_em))*86400 END) AS primeira,
                 AVG(c.avaliacao) AS csat
               FROM conversas c JOIN usuarios u ON u.id=c.responsavel_id
               WHERE c.empresa_id=? AND c.criada_em>=?""" + fcc + """ GROUP BY u.id ORDER BY atendimentos DESC""",
            (empresa_id, inicio, *pc),
        )
        canais = self.banco.todos(
            "SELECT canal, COUNT(*) AS atendimentos, SUM(CASE WHEN status='resolvido' THEN 1 ELSE 0 END) AS resolvidos FROM conversas WHERE empresa_id=? AND criada_em>=?" + fc + " GROUP BY canal",
            (empresa_id, inicio, *pc),
        )
        notas = {n["avaliacao"]: n["quantidade"] for n in self.banco.todos(
            "SELECT avaliacao, COUNT(*) AS quantidade FROM conversas WHERE empresa_id=? AND avaliacao IS NOT NULL AND criada_em>=?" + fc + " GROUP BY avaliacao",
            (empresa_id, inicio, *pc))}
        for linha in equipe:
            linha["tempo_primeira_resposta"] = _minutos_segundos(linha.pop("primeira"))
            linha["csat"] = round(linha["csat"], 1) if linha["csat"] else None
        return {
            "dias": dias,
            "kpis": {
                "resolvidos": base.get("resolvidos") or 0, "atendimentos": base.get("total") or 0,
                "conversao": conversao, "csat": round(base["csat"], 1) if base.get("avaliacoes") else None,
                "tempo_primeira_resposta": _minutos_segundos(base.get("primeira")), "mensagens": mensagens,
            },
            "equipe": equipe, "canais": canais, "orcamentos": orc,
            "csat": [{"nota": n, "quantidade": notas.get(n, 0)} for n in range(1, 6)],
        }

    def relatorio_csv(self, ator: Ator, tipo: str, dias: int = 30) -> str:
        ator.exigir("relatorios", "exportar")
        dados = self.relatorio(ator, dias)
        tabelas = {
            "equipe": (("nome", "atendimentos", "resolvidos", "tempo_primeira_resposta", "csat"), dados["equipe"]),
            "canais": (("canal", "atendimentos", "resolvidos"), dados["canais"]),
            "orcamentos": (("status", "quantidade", "valor"), [{**o, "valor": f"{(o['valor'] or 0) / 100:.2f}"} for o in dados["orcamentos"]]),
            "csat": (("nota", "quantidade"), dados["csat"]),
        }
        if tipo not in tabelas:
            raise ErroNegocio("Relatório desconhecido.")
        colunas, linhas = tabelas[tipo]
        saida = io.StringIO()
        escritor = csv.writer(saida, delimiter=";")
        escritor.writerow(colunas)
        for linha in linhas:
            escritor.writerow([linha.get(c) if linha.get(c) is not None else "" for c in colunas])
        self.auditar(ator, "relatorio.exportar", tipo, {"dias": dias})
        return "﻿" + saida.getvalue()

    # ================================================================ BACKUP
    def _pasta_backups(self, empresa_id: str) -> Path:
        pasta = Path(self.pasta_backups or (pasta_dados() / "backups")) / empresa_id
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def _colunas(self, tabela: str) -> list[str]:
        with self.banco.conexao() as c:
            return [linha["name"] for linha in c.execute(f"PRAGMA table_info({tabela})").fetchall()]

    def exportar_dados(self, empresa_id: str) -> dict:
        empresa = self.obter_empresa(empresa_id)
        tabelas = {}
        for tabela in TABELAS_BACKUP:
            tabelas[tabela] = self.banco.todos(f"SELECT * FROM {tabela} WHERE empresa_id=?", (empresa_id,))
        for usuario in tabelas.get("usuarios") or []:  # o segredo do código do celular nunca sai do servidor
            for campo in ("totp_segredo", "totp_ativo", "totp_ultimo"):
                usuario.pop(campo, None)
        tabelas["contadores"] = self.banco.todos("SELECT * FROM contadores WHERE empresa_id=?", (empresa_id,))
        return {"formato": FORMATO_BACKUP, "versao": 1, "criado_em": agora(),
                "empresa": {"id": empresa_id, "nome": empresa["nome"]}, "tabelas": tabelas}

    def criar_backup(self, ator: Ator | None, empresa_id: str | None = None, tipo: str = "manual") -> dict:
        if ator is not None:
            ator.exigir("backup", "criar")
            empresa_id = ator.empresa
        dados = self.exportar_dados(empresa_id)
        conteudo = json.dumps(dados, ensure_ascii=False, indent=1).encode("utf-8")
        nome = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{tipo}.json"
        arquivo = self._pasta_backups(empresa_id) / nome
        arquivo.write_bytes(conteudo)
        backup_id = novo_id()
        self.banco.executar("INSERT INTO backups(id, empresa_id, arquivo, tipo, tamanho, criado_em) VALUES (?,?,?,?,?,?)",
                            (backup_id, empresa_id, nome, tipo, len(conteudo), agora()))
        if tipo == "automatico":
            antigos = self.banco.todos("SELECT id, arquivo FROM backups WHERE empresa_id=? AND tipo='automatico' ORDER BY criado_em DESC", (empresa_id,))
            for velho in antigos[MANTER_BACKUPS_AUTOMATICOS:]:
                (self._pasta_backups(empresa_id) / velho["arquivo"]).unlink(missing_ok=True)
                self.banco.executar("DELETE FROM backups WHERE id=?", (velho["id"],))
        self.auditar(ator, "backup.criar", backup_id, {"tipo": tipo}, empresa_id=empresa_id)
        return self.banco.um("SELECT * FROM backups WHERE id=?", (backup_id,))

    def listar_backups(self, ator: Ator) -> list[dict]:
        ator.exigir("backup", "ver")
        return self.banco.todos("SELECT * FROM backups WHERE empresa_id=? ORDER BY criado_em DESC LIMIT 60", (ator.empresa,))

    def baixar_backup(self, ator: Ator, backup_id: str) -> tuple[str, bytes]:
        ator.exigir("backup", "ver")
        backup = self.banco.um("SELECT * FROM backups WHERE id=? AND empresa_id=?", (backup_id, ator.empresa))
        if not backup:
            raise NaoEncontrado("Backup não encontrado.")
        caminho = self._pasta_backups(ator.empresa) / backup["arquivo"]
        if not caminho.exists():
            raise NaoEncontrado("O arquivo desse backup não está mais na pasta.")
        self.auditar(ator, "backup.baixar", backup_id)
        return backup["arquivo"], caminho.read_bytes()

    def _validar_backup(self, ator: Ator, dados: dict) -> dict:
        if not isinstance(dados, dict) or dados.get("formato") != FORMATO_BACKUP or not isinstance(dados.get("tabelas"), dict):
            raise ErroNegocio("Arquivo de backup inválido.")
        if (dados.get("empresa") or {}).get("id") != ator.empresa:
            raise ErroNegocio("Este backup é de outra empresa e não pode ser restaurado aqui.")
        return dados["tabelas"]

    def previa_restauracao(self, ator: Ator, dados: dict) -> dict:
        ator.exigir("backup", "restaurar")
        tabelas = self._validar_backup(ator, dados)
        resumo = []
        for tabela in TABELAS_BACKUP:
            linhas = tabelas.get(tabela) or []
            ids = [l.get("id") for l in linhas if isinstance(l, dict) and l.get("id")]
            existentes = 0
            for inicio in range(0, len(ids), 500):
                parte = ids[inicio:inicio + 500]
                marcadores = ",".join("?" * len(parte))
                existentes += self.banco.um(f"SELECT COUNT(*) AS n FROM {tabela} WHERE id IN ({marcadores})", parte)["n"]
            resumo.append({"tabela": tabela, "no_backup": len(ids), "ja_existem": existentes, "serao_adicionados": len(ids) - existentes})
        return {"resumo": resumo, "modo": "mesclar",
                "explicacao": "Só entram registros que não existem hoje. Nada que já está no sistema é apagado ou substituído."}

    def restaurar_backup(self, ator: Ator, dados: dict) -> dict:
        ator.exigir("backup", "restaurar")
        tabelas = self._validar_backup(ator, dados)
        self.criar_backup(ator, tipo="antes-da-restauracao")
        adicionados = {}
        with self.banco.transacao() as c:
            for tabela in TABELAS_BACKUP:
                colunas_validas = set(self._colunas(tabela))
                total = 0
                for linha in tabelas.get(tabela) or []:
                    if not isinstance(linha, dict) or linha.get("empresa_id") != ator.empresa:
                        continue
                    colunas = [k for k in linha if k in colunas_validas]
                    sql = f"INSERT OR IGNORE INTO {tabela}({','.join(colunas)}) VALUES ({','.join('?' * len(colunas))})"
                    total += c.execute(sql, [linha[k] for k in colunas]).rowcount
                adicionados[tabela] = total
            for contador in tabelas.get("contadores") or []:
                if isinstance(contador, dict) and contador.get("empresa_id") == ator.empresa:
                    c.execute(
                        "INSERT INTO contadores(empresa_id, nome, valor) VALUES (?,?,?) ON CONFLICT(empresa_id, nome) DO UPDATE SET valor=MAX(valor, excluded.valor)",
                        (ator.empresa, str(contador.get("nome")), int(contador.get("valor") or 0)),
                    )
        self.auditar(ator, "backup.restaurar", None, adicionados)
        return {"adicionados": adicionados}

    # ================================================================ ROTINA (a cada minuto)
    def rotina(self) -> None:
        for empresa in self.banco.todos("SELECT id FROM empresas WHERE ativa=1"):
            try:
                self.gerar_alertas(empresa["id"])
                hoje = date.today().isoformat()
                if not self.banco.um("SELECT 1 AS x FROM backups WHERE empresa_id=? AND tipo='automatico' AND substr(criado_em,1,10)=?",
                                     (empresa["id"], hoje)):
                    self.criar_backup(None, empresa["id"], "automatico")
            except Exception:  # noqa: BLE001 - uma empresa com problema não para as outras
                continue
