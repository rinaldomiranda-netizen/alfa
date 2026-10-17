"""WhatsApp oficial (Meta Cloud API), API pública V1 e webhooks de saída.

WhatsApp:
- Recebe mensagens no endereço /webhooks/whatsapp (a Meta chama esse
  endereço). Toda chamada é conferida com a assinatura HMAC
  (X-Hub-Signature-256) usando o "App Secret" do seu aplicativo Meta.
- Envia texto, botões (até 3 opções) e listas (até 10 opções).
- A Meta só aceita mensagem livre até 24 h depois da última mensagem do
  cliente; fora disso é preciso um modelo (template) aprovado.

Webhooks de saída: só HTTPS, nunca para endereços internos da rede
(proteção contra SSRF), assinatura HMAC opcional e registro de cada
entrega.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from . import seguranca
from .conversas import normalizar_telefone
from .db import agora, somar_minutos
from .nucleo import Ator, ErroNegocio, NaoAutenticado, NaoEncontrado, _texto, novo_id

GRAPH = "https://graph.facebook.com"
ESCOPOS_API = ("names:read", "names:write", "messages:write", "conversations:read")
NOMES_ESCOPOS = {
    "names:read": "Leitura de nomes",
    "names:write": "Cadastro e alteração de nomes",
    "messages:write": "Envio de mensagens",
    "conversations:read": "Leitura de atendimentos",
}
EVENTOS = ("atendimento.criado", "mensagem.recebida", "atendimento.resolvido", "nome.criado",
           "orcamento.aprovado", "orcamento.recusado")


class _SemRedirecionamento(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - nunca segue redirecionamento
        return None


_ABRIDOR = urllib.request.build_opener(_SemRedirecionamento)


def http_padrao(metodo: str, url: str, cabecalhos: dict, corpo: bytes | None, timeout: int = 10) -> tuple[int, bytes]:
    requisicao = urllib.request.Request(url, data=corpo, headers=cabecalhos, method=metodo)
    try:
        with _ABRIDOR.open(requisicao, timeout=timeout) as resposta:
            return resposta.status, resposta.read(1_000_000)
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read(1_000_000) if erro.fp else b""


def endereco_externo_seguro(url: str) -> str | None:
    """Devolve None se a URL for segura para receber webhook; senão, o motivo."""
    try:
        partes = urllib.parse.urlsplit(url)
    except ValueError:
        return "Endereço inválido."
    if partes.scheme != "https":
        return "O endereço precisa começar com https://"
    if not partes.hostname or partes.username or partes.password:
        return "Endereço inválido."
    try:
        enderecos = {info[4][0] for info in socket.getaddrinfo(partes.hostname, partes.port or 443, proto=socket.IPPROTO_TCP)}
    except socket.gaierror:
        return "Não foi possível encontrar esse endereço na internet."
    for endereco in enderecos:
        ip = ipaddress.ip_address(endereco.split("%")[0])
        if not ip.is_global or ip.is_multicast:
            return "Endereços internos (rede local, localhost) não são permitidos."
    return None


def _mascarar(valor: str | None) -> str | None:
    if not valor:
        return None
    return valor[:4] + "…" + valor[-4:] if len(valor) > 10 else "••••"


class CanaisMixin:
    envio_sincrono = False  # testes usam True para não criar threads

    # ================================================================ WHATSAPP — configuração
    @staticmethod
    def _canal_publico(canal: dict) -> dict:
        return {
            **{k: canal[k] for k in ("id", "nome", "numero_exibicao", "phone_number_id", "waba_id", "versao_api", "ativo", "ultimo_evento_em", "criado_em")},
            "access_token": _mascarar(canal["access_token"]), "app_secret": _mascarar(canal["app_secret"]),
            "verify_token": canal["verify_token"],
        }

    def _canal_whatsapp_ativo(self, empresa_id: str) -> dict | None:
        return self.banco.um("SELECT * FROM whatsapp_canais WHERE empresa_id=? AND ativo=1 ORDER BY criado_em LIMIT 1", (empresa_id,))

    def whatsapp_painel(self, ator: Ator) -> dict:
        ator.exigir("whatsapp", "ver")
        hoje = date.today().isoformat()
        canais = [self._canal_publico(c) for c in self.banco.todos("SELECT * FROM whatsapp_canais WHERE empresa_id=? ORDER BY criado_em", (ator.empresa,))]
        contagem = self.banco.um(
            """SELECT
                 SUM(CASE WHEN m.direcao='entrada' THEN 1 ELSE 0 END) AS recebidas,
                 SUM(CASE WHEN m.direcao='saida' THEN 1 ELSE 0 END) AS enviadas,
                 SUM(CASE WHEN m.status_entrega='enviado' THEN 1 ELSE 0 END) AS sent,
                 SUM(CASE WHEN m.status_entrega='entregue' THEN 1 ELSE 0 END) AS delivered,
                 SUM(CASE WHEN m.status_entrega='lido' THEN 1 ELSE 0 END) AS lidas,
                 SUM(CASE WHEN m.status_entrega='falhou' THEN 1 ELSE 0 END) AS falhas
               FROM mensagens m JOIN conversas c ON c.id=m.conversa_id
               WHERE m.empresa_id=? AND c.canal='whatsapp' AND substr(m.criada_em,1,10)=?""",
            (ator.empresa, hoje),
        ) or {}
        return {"canais": canais, "hoje": {k: int(v or 0) for k, v in contagem.items()},
                "endereco_webhook": "/webhooks/whatsapp"}

    def salvar_canal_whatsapp(self, ator: Ator, dados: dict, canal_id: str | None = None) -> dict:
        ator.exigir("whatsapp", "configurar")
        atual = None
        if canal_id:
            atual = self.banco.um("SELECT * FROM whatsapp_canais WHERE id=? AND empresa_id=?", (canal_id, ator.empresa))
            if not atual:
                raise NaoEncontrado("Canal não encontrado.")
        nome = _texto(dados.get("nome") or (atual or {}).get("nome") or "WhatsApp", "nome", maximo=60)
        phone_number_id = _texto(dados.get("phone_number_id") or (atual or {}).get("phone_number_id"), "Phone number ID", maximo=40)
        if not phone_number_id.isdigit():
            raise ErroNegocio("O Phone number ID tem só números (veja no painel da Meta, em WhatsApp > Configuração da API).")
        token = (dados.get("access_token") or "").strip() or (atual or {}).get("access_token")
        if not token:
            raise ErroNegocio("Informe o token de acesso (access token) da Meta.")
        segredo = (dados.get("app_secret") or "").strip() or (atual or {}).get("app_secret")
        if not segredo:
            raise ErroNegocio("Informe o App Secret do aplicativo Meta (usado para conferir que a mensagem veio mesmo da Meta).")
        dono = self.banco.um("SELECT empresa_id FROM whatsapp_canais WHERE phone_number_id=? AND id<>?", (phone_number_id, canal_id or ""))
        if dono:
            raise ErroNegocio("Esse número já está ligado a outra empresa.")
        valores = {
            "nome": nome, "numero_exibicao": _texto(dados.get("numero_exibicao") or (atual or {}).get("numero_exibicao"), "número", False, 30),
            "phone_number_id": phone_number_id, "waba_id": _texto(dados.get("waba_id") or (atual or {}).get("waba_id"), "WABA ID", False, 40),
            "access_token": token, "app_secret": segredo,
            "versao_api": (dados.get("versao_api") or (atual or {}).get("versao_api") or "v21.0").strip(),
            "ativo": 1 if dados.get("ativo", (atual or {}).get("ativo", 1)) else 0,
        }
        if not valores["versao_api"].startswith("v"):
            raise ErroNegocio("Versão da API inválida (ex.: v21.0).")
        if canal_id:
            self.banco.executar(
                """UPDATE whatsapp_canais SET nome=:nome, numero_exibicao=:numero_exibicao, phone_number_id=:phone_number_id, waba_id=:waba_id,
                   access_token=:access_token, app_secret=:app_secret, versao_api=:versao_api, ativo=:ativo WHERE id=:id""",
                {**valores, "id": canal_id},
            )
        else:
            canal_id = novo_id()
            self.banco.executar(
                """INSERT INTO whatsapp_canais(id, empresa_id, nome, numero_exibicao, phone_number_id, waba_id, access_token, app_secret,
                   verify_token, versao_api, ativo, criado_em) VALUES (:id,:empresa,:nome,:numero_exibicao,:phone_number_id,:waba_id,
                   :access_token,:app_secret,:verify,:versao_api,:ativo,:agora)""",
                {**valores, "id": canal_id, "empresa": ator.empresa, "verify": secrets.token_urlsafe(18), "agora": agora()},
            )
        self.auditar(ator, "whatsapp.salvar", canal_id, {"phone_number_id": phone_number_id, "ativo": valores["ativo"]})
        self._verificar_limite_canais(ator.empresa)
        return self._canal_publico(self.banco.um("SELECT * FROM whatsapp_canais WHERE id=?", (canal_id,)))

    # ================================================================ WHATSAPP — envio
    def _enviar_whatsapp(self, canal: dict, para: str, corpo: dict) -> tuple[bool, str | None, str | None]:
        url = f"{GRAPH}/{canal['versao_api']}/{canal['phone_number_id']}/messages"
        dados = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": para, **corpo}
        try:
            status, resposta = self.http("POST", url, {
                "Authorization": f"Bearer {canal['access_token']}", "Content-Type": "application/json",
            }, json.dumps(dados).encode("utf-8"))
        except (OSError, ValueError) as erro:
            return False, None, f"Sem conexão com a Meta: {erro}"
        try:
            conteudo = json.loads(resposta.decode("utf-8") or "{}")
        except ValueError:
            conteudo = {}
        if 200 <= status < 300 and conteudo.get("messages"):
            return True, conteudo["messages"][0].get("id"), None
        erro = (conteudo.get("error") or {})
        detalhe = erro.get("error_user_msg") or erro.get("message") or f"HTTP {status}"
        if erro.get("code") == 131047:
            detalhe = "Passaram mais de 24 h desde a última mensagem do cliente. A Meta exige um modelo (template) aprovado."
        return False, None, detalhe

    @staticmethod
    def _corpo_whatsapp(texto: str, opcoes: list[str]) -> dict:
        if opcoes and len(opcoes) <= 3 and all(len(o) <= 20 for o in opcoes):
            return {"type": "interactive", "interactive": {
                "type": "button", "body": {"text": texto[:1024]},
                "action": {"buttons": [{"type": "reply", "reply": {"id": f"op{n}", "title": o}} for n, o in enumerate(opcoes, 1)]},
            }}
        if opcoes and len(opcoes) <= 10:
            return {"type": "interactive", "interactive": {
                "type": "list", "body": {"text": texto[:1024]},
                "action": {"button": "Ver opções", "sections": [{"title": "Opções", "rows": [
                    {"id": f"op{n}", "title": o[:24]} for n, o in enumerate(opcoes, 1)]}]},
            }}
        if opcoes:
            texto = texto + "\n" + "\n".join(f"{n}. {o}" for n, o in enumerate(opcoes, 1))
        return {"type": "text", "text": {"body": texto[:4096], "preview_url": False}}

    def _entregar(self, conversa: dict, mensagem: dict, texto: str, opcoes: list[str]) -> None:
        """Leva a mensagem de saída até o cliente pelo canal da conversa."""
        if conversa["canal"] != "whatsapp":
            self.banco.executar("UPDATE mensagens SET status_entrega='entregue' WHERE id=?", (mensagem["id"],))
            return
        canal = (self.banco.um("SELECT * FROM whatsapp_canais WHERE id=? AND ativo=1", (conversa["canal_id"],)) if conversa.get("canal_id") else None) \
            or self._canal_whatsapp_ativo(conversa["empresa_id"])
        contato = self.banco.um("SELECT whatsapp FROM contatos WHERE id=?", (conversa["contato_id"],)) or {}
        if not canal or not contato.get("whatsapp"):
            motivo = "Nenhum número de WhatsApp ativo configurado." if not canal else "O nome não tem WhatsApp cadastrado."
            self.banco.executar("UPDATE mensagens SET status_entrega='falhou', erro=? WHERE id=?", (motivo, mensagem["id"]))
            self._alerta_falha_whatsapp(conversa, mensagem["id"], motivo)
            return
        ok, externo_id, erro = self._enviar_whatsapp(canal, contato["whatsapp"], self._corpo_whatsapp(texto, opcoes))
        self.banco.executar(
            "UPDATE mensagens SET status_entrega=?, externo_id=?, erro=? WHERE id=?",
            ("enviado" if ok else "falhou", externo_id, erro, mensagem["id"]),
        )
        if not ok:
            self._alerta_falha_whatsapp(conversa, mensagem["id"], erro)

    def _alerta_falha_whatsapp(self, conversa: dict, mensagem_id: str, motivo: str | None) -> None:
        self._novo_alerta(conversa["empresa_id"], f"whatsapp-falha:{mensagem_id}", "whatsapp", "atencao",
                          "Falha de entrega no WhatsApp", f"Atendimento #{conversa['numero']}: {motivo}", conversa["id"])

    def testar_whatsapp(self, ator: Ator, canal_id: str, numero: str, texto: str | None = None) -> dict:
        ator.exigir("whatsapp", "testar")
        canal = self.banco.um("SELECT * FROM whatsapp_canais WHERE id=? AND empresa_id=?", (canal_id, ator.empresa))
        if not canal:
            raise NaoEncontrado("Canal não encontrado.")
        para = normalizar_telefone(numero)
        if not para:
            raise ErroNegocio("Informe o número de destino com DDD.")
        if texto:
            corpo = self._corpo_whatsapp(texto, [])
        else:
            corpo = {"type": "template", "template": {"name": "hello_world", "language": {"code": "en_US"}}}
        ok, externo_id, erro = self._enviar_whatsapp(canal, para, corpo)
        self.auditar(ator, "whatsapp.testar", canal_id, {"ok": ok, "erro": erro})
        return {"ok": ok, "id_meta": externo_id, "erro": erro,
                "modelo": None if texto else "hello_world"}

    # ================================================================ WHATSAPP — recebimento (webhook)
    def whatsapp_verificar_webhook(self, modo: str, token: str, desafio: str) -> str | None:
        if modo != "subscribe" or not token:
            return None
        canal = self.banco.um("SELECT id FROM whatsapp_canais WHERE verify_token=?", (token,))
        return desafio if canal else None

    def whatsapp_receber(self, corpo_bruto: bytes, assinatura: str | None) -> int:
        """Processa a chamada da Meta. Devolve quantos eventos foram aceitos.
        Levanta NaoAutenticado se a assinatura não conferir."""
        try:
            dados = json.loads(corpo_bruto.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ErroNegocio("Conteúdo inválido.") from None
        aceitos = 0
        for entrada in dados.get("entry", []) or []:
            for mudanca in entrada.get("changes", []) or []:
                valor = mudanca.get("value") or {}
                phone_number_id = str((valor.get("metadata") or {}).get("phone_number_id") or "")
                canal = self.banco.um("SELECT * FROM whatsapp_canais WHERE phone_number_id=? AND ativo=1", (phone_number_id,))
                if not canal:
                    continue
                esperado = "sha256=" + hmac.new((canal["app_secret"] or "").encode(), corpo_bruto, hashlib.sha256).hexdigest()
                if not canal["app_secret"] or not assinatura or not hmac.compare_digest(esperado, assinatura.strip()):
                    self.auditar(None, "whatsapp.assinatura_invalida", canal["id"], empresa_id=canal["empresa_id"])
                    raise NaoAutenticado("Assinatura da Meta inválida.")
                self.banco.executar("UPDATE whatsapp_canais SET ultimo_evento_em=? WHERE id=?", (agora(), canal["id"]))
                perfis = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in valor.get("contacts", []) or []}
                for mensagem in valor.get("messages", []) or []:
                    aceitos += self._whatsapp_mensagem(canal, mensagem, perfis)
                for status in valor.get("statuses", []) or []:
                    aceitos += self._whatsapp_status(canal, status)
        return aceitos

    def _whatsapp_mensagem(self, canal: dict, mensagem: dict, perfis: dict) -> int:
        externo_id = mensagem.get("id")
        if externo_id and self.banco.um("SELECT 1 AS x FROM mensagens WHERE externo_id=? AND direcao='entrada'", (externo_id,)):
            return 0  # a Meta pode reenviar o mesmo evento
        de = normalizar_telefone(mensagem.get("from"))
        if not de:
            return 0
        tipo = mensagem.get("type")
        if tipo == "text":
            texto = (mensagem.get("text") or {}).get("body", "")
        elif tipo == "interactive":
            interativo = mensagem.get("interactive") or {}
            resposta = interativo.get("button_reply") or interativo.get("list_reply") or {}
            texto = resposta.get("title", "")
        elif tipo == "button":
            texto = (mensagem.get("button") or {}).get("text", "")
        else:
            texto = f"[{tipo or 'mensagem'} recebido — abra no WhatsApp para ver]"
        empresa_id = canal["empresa_id"]
        contato = self.banco.um("SELECT * FROM contatos WHERE empresa_id=? AND whatsapp=?", (empresa_id, de))
        if not contato:
            contato = self._criar_contato(empresa_id, {"nome": perfis.get(mensagem.get("from")) or f"+{de}", "telefone": de, "tags": ["whatsapp"]})
        conversa_aberta = self.banco.um(
            "SELECT * FROM conversas WHERE contato_id=? AND canal='whatsapp' AND status='resolvido' AND avaliacao IS NULL AND resolvida_em >= ? ORDER BY resolvida_em DESC LIMIT 1",
            (contato["id"], somar_minutos(agora(), -24 * 60)),
        )
        tem_aberta = self.banco.um("SELECT 1 AS x FROM conversas WHERE contato_id=? AND canal='whatsapp' AND status<>'resolvido'", (contato["id"],))
        if conversa_aberta and not tem_aberta and self.registrar_avaliacao(empresa_id, conversa_aberta["id"], texto):
            self._gravar_mensagem(conversa_aberta, "entrada", "contato", texto, autor_id=contato["id"], externo_id=externo_id)
            return 1
        self.receber_mensagem(empresa_id, contato["id"], "whatsapp", texto, canal_id=canal["id"], externo_id=externo_id,
                              payload={"tipo": tipo})
        return 1

    def _whatsapp_status(self, canal: dict, status: dict) -> int:
        mapa = {"sent": "enviado", "delivered": "entregue", "read": "lido", "failed": "falhou"}
        novo = mapa.get(status.get("status"))
        if not novo or not status.get("id"):
            return 0
        erro = None
        if novo == "falhou":
            erros = status.get("errors") or [{}]
            erro = erros[0].get("title") or erros[0].get("message") or "Falha de entrega"
        mensagem = self.banco.um("SELECT m.*, c.numero FROM mensagens m JOIN conversas c ON c.id=m.conversa_id WHERE m.externo_id=? AND m.empresa_id=?",
                                 (status["id"], canal["empresa_id"]))
        if not mensagem:
            return 0
        ordem = ("enviado", "entregue", "lido")
        if novo != "falhou" and mensagem["status_entrega"] in ordem and ordem.index(mensagem["status_entrega"]) >= ordem.index(novo):
            return 0
        self.banco.executar("UPDATE mensagens SET status_entrega=?, erro=COALESCE(?, erro) WHERE id=?", (novo, erro, mensagem["id"]))
        if novo == "falhou":
            self._alerta_falha_whatsapp({"empresa_id": canal["empresa_id"], "numero": mensagem["numero"], "id": mensagem["conversa_id"]},
                                        mensagem["id"], erro)
        return 1

    # ================================================================ API PÚBLICA V1
    def listar_chaves_api(self, ator: Ator) -> list[dict]:
        ator.exigir("api", "ver")
        linhas = self.banco.todos(
            "SELECT id, nome, prefixo, escopos, dry_run, ativa, ultimo_uso, criada_em FROM api_chaves WHERE empresa_id=? ORDER BY criada_em DESC",
            (ator.empresa,),
        )
        return [{**l, "escopos": json.loads(l["escopos"])} for l in linhas]

    def criar_chave_api(self, ator: Ator, nome: str, escopos: list[str], dry_run: bool = True) -> dict:
        ator.exigir("api", "configurar")
        nome = _texto(nome, "nome da chave", maximo=60)
        escopos = sorted(set(escopos or []))
        if not escopos or any(e not in ESCOPOS_API for e in escopos):
            raise ErroNegocio("Escolha pelo menos uma permissão válida.")
        chave, prefixo, hash_chave = seguranca.nova_chave_api()
        chave_id = novo_id()
        self.banco.executar(
            "INSERT INTO api_chaves(id, empresa_id, nome, prefixo, chave_hash, escopos, dry_run, criada_em) VALUES (?,?,?,?,?,?,?,?)",
            (chave_id, ator.empresa, nome, prefixo, hash_chave, json.dumps(escopos), 1 if dry_run else 0, agora()),
        )
        self.auditar(ator, "api.chave_criar", chave_id, {"escopos": escopos, "dry_run": dry_run})
        return {"id": chave_id, "chave": chave, "aviso": "Copie agora: esta chave não será mostrada de novo."}

    def alterar_chave_api(self, ator: Ator, chave_id: str, ativa: bool | None = None, dry_run: bool | None = None) -> None:
        ator.exigir("api", "configurar")
        if not self.banco.um("SELECT 1 AS x FROM api_chaves WHERE id=? AND empresa_id=?", (chave_id, ator.empresa)):
            raise NaoEncontrado("Chave não encontrada.")
        if ativa is not None:
            self.banco.executar("UPDATE api_chaves SET ativa=? WHERE id=?", (1 if ativa else 0, chave_id))
        if dry_run is not None:
            self.banco.executar("UPDATE api_chaves SET dry_run=? WHERE id=?", (1 if dry_run else 0, chave_id))
        self.auditar(ator, "api.chave_alterar", chave_id, {"ativa": ativa, "dry_run": dry_run})

    def autenticar_chave_api(self, chave: str, escopo: str) -> dict:
        prefixo = seguranca.separar_prefixo(chave or "")
        registro = self.banco.um("SELECT * FROM api_chaves WHERE prefixo=? AND ativa=1", (prefixo or "",)) if prefixo else None
        if not registro or not hmac.compare_digest(registro["chave_hash"], seguranca.hash_token(chave)):
            raise NaoAutenticado("Chave de API inválida.")
        if escopo not in json.loads(registro["escopos"]):
            raise NaoAutenticado(f"Esta chave não tem a permissão '{escopo}'.")
        self.banco.executar("UPDATE api_chaves SET ultimo_uso=? WHERE id=?", (agora(), registro["id"]))
        return registro

    def api_listar_nomes(self, chave: dict, busca: str = "") -> list[dict]:
        sql = "SELECT id, nome, telefone, whatsapp, email, tags, status, criado_em FROM contatos WHERE empresa_id=?"
        parametros: list = [chave["empresa_id"]]
        if busca:
            sql += " AND (nome LIKE ? OR telefone LIKE ?)"
            parametros += [f"%{busca}%", f"%{busca}%"]
        return [{**c, "tags": json.loads(c["tags"])} for c in self.banco.todos(sql + " ORDER BY criado_em DESC LIMIT 200", parametros)]

    def api_criar_nome(self, chave: dict, dados: dict) -> dict:
        if chave["dry_run"]:
            valores = self._limpar_contato(dados)
            return {"dry_run": True, "criaria": {**valores, "tags": json.loads(valores["tags"])}}
        contato = self._criar_contato(chave["empresa_id"], dados)
        self.auditar(None, "api.nome_criar", contato["id"], {"chave": chave["prefixo"]}, empresa_id=chave["empresa_id"])
        return contato

    def api_enviar_mensagem(self, chave: dict, telefone: str, texto: str) -> dict:
        texto = _texto(texto, "texto", maximo=4000)
        para = normalizar_telefone(telefone)
        if not para:
            raise ErroNegocio("Telefone inválido.")
        contato = self.banco.um("SELECT * FROM contatos WHERE empresa_id=? AND whatsapp=?", (chave["empresa_id"], para))
        if chave["dry_run"]:
            return {"dry_run": True, "enviaria": {"para": para, "texto": texto, "nome_cadastrado": bool(contato),
                                                  "canal_ativo": bool(self._canal_whatsapp_ativo(chave["empresa_id"]))}}
        if not self._canal_whatsapp_ativo(chave["empresa_id"]):
            raise ErroNegocio("Nenhum número de WhatsApp ativo configurado.")
        if not contato:
            contato = self._criar_contato(chave["empresa_id"], {"nome": f"+{para}", "telefone": para, "tags": ["api"]})
        conversa = self.banco.um(
            "SELECT * FROM conversas WHERE contato_id=? AND canal='whatsapp' AND status<>'resolvido' ORDER BY criada_em DESC LIMIT 1",
            (contato["id"],),
        ) or self._nova_conversa(chave["empresa_id"], contato["id"], "whatsapp")
        mensagem = self._gravar_mensagem(conversa, "saida", "sistema", texto, autor_id=chave["prefixo"])
        self._entregar(conversa, mensagem, texto, [])
        final = self.banco.um("SELECT id, status_entrega, erro FROM mensagens WHERE id=?", (mensagem["id"],))
        self.auditar(None, "api.mensagem_enviar", mensagem["id"], {"chave": chave["prefixo"]}, empresa_id=chave["empresa_id"])
        return {"dry_run": False, "mensagem": final}

    # ================================================================ WEBHOOKS DE SAÍDA
    def listar_webhooks(self, ator: Ator) -> list[dict]:
        ator.exigir("api", "ver")
        ganchos = self.banco.todos("SELECT id, url, eventos, segredo, ativo, criado_em FROM webhooks WHERE empresa_id=? ORDER BY criado_em DESC", (ator.empresa,))
        for g in ganchos:
            g["eventos"] = json.loads(g["eventos"])
            g["assinado"] = bool(g.pop("segredo"))
            g["entregas"] = self.banco.todos(
                "SELECT evento, ok, codigo_http, erro, criada_em FROM webhook_entregas WHERE webhook_id=? ORDER BY criada_em DESC LIMIT 10", (g["id"],))
        return ganchos

    def criar_webhook(self, ator: Ator, url: str, eventos: list[str], assinar: bool = True) -> dict:
        ator.exigir("api", "configurar")
        url = _texto(url, "endereço", maximo=500)
        motivo = endereco_externo_seguro(url)
        if motivo:
            raise ErroNegocio(motivo)
        eventos = sorted(set(eventos or []))
        if not eventos or any(e not in EVENTOS for e in eventos):
            raise ErroNegocio("Escolha pelo menos um evento válido.")
        segredo = secrets.token_hex(24) if assinar else None
        gancho_id = novo_id()
        self.banco.executar("INSERT INTO webhooks(id, empresa_id, url, eventos, segredo, ativo, criado_em) VALUES (?,?,?,?,?,1,?)",
                            (gancho_id, ator.empresa, url, json.dumps(eventos), segredo, agora()))
        self.auditar(ator, "webhook.criar", gancho_id, {"url": url, "eventos": eventos})
        return {"id": gancho_id, "segredo": segredo,
                "aviso": "Guarde o segredo: ele assina cada envio no cabeçalho X-RMD-Assinatura (sha256=...)." if segredo else None}

    def alterar_webhook(self, ator: Ator, gancho_id: str, ativo: bool) -> None:
        ator.exigir("api", "configurar")
        if not self.banco.executar("UPDATE webhooks SET ativo=? WHERE id=? AND empresa_id=?", (1 if ativo else 0, gancho_id, ator.empresa)):
            raise NaoEncontrado("Webhook não encontrado.")
        self.auditar(ator, "webhook.alterar", gancho_id, {"ativo": ativo})

    def testar_webhook(self, ator: Ator, gancho_id: str) -> dict:
        ator.exigir("api", "configurar")
        gancho = self.banco.um("SELECT * FROM webhooks WHERE id=? AND empresa_id=?", (gancho_id, ator.empresa))
        if not gancho:
            raise NaoEncontrado("Webhook não encontrado.")
        return self._entregar_webhook(gancho, "teste.ping", {"mensagem": "Teste do RMD Atendimento"})

    def disparar_evento(self, empresa_id: str, evento: str, dados: dict) -> None:
        ganchos = [g for g in self.banco.todos("SELECT * FROM webhooks WHERE empresa_id=? AND ativo=1", (empresa_id,))
                   if evento in json.loads(g["eventos"])]
        if not ganchos:
            return

        def enviar():
            for gancho in ganchos:
                try:
                    self._entregar_webhook(gancho, evento, dados)
                except Exception:  # noqa: BLE001 - um webhook com erro nunca derruba o atendimento
                    pass

        if self.envio_sincrono:
            enviar()
        else:
            threading.Thread(target=enviar, daemon=True, name="RMDWebhook").start()

    def _entregar_webhook(self, gancho: dict, evento: str, dados: dict) -> dict:
        corpo = json.dumps({"evento": evento, "empresa_id": gancho["empresa_id"], "enviado_em": agora(), "dados": dados},
                           ensure_ascii=False).encode("utf-8")
        cabecalhos = {"Content-Type": "application/json", "User-Agent": "RMD-Atendimento-Webhook/1", "X-RMD-Evento": evento}
        if gancho["segredo"]:
            cabecalhos["X-RMD-Assinatura"] = "sha256=" + hmac.new(gancho["segredo"].encode(), corpo, hashlib.sha256).hexdigest()
        motivo = endereco_externo_seguro(gancho["url"])
        codigo, erro = None, motivo
        if not motivo:
            try:
                codigo, _ = self.http("POST", gancho["url"], cabecalhos, corpo, 8)
                erro = None if 200 <= codigo < 300 else f"Resposta HTTP {codigo}"
            except (OSError, ValueError) as falha:
                erro = str(falha)[:200]
        ok = erro is None
        self.banco.executar(
            "INSERT INTO webhook_entregas(id, empresa_id, webhook_id, evento, ok, codigo_http, erro, criada_em) VALUES (?,?,?,?,?,?,?,?)",
            (novo_id(), gancho["empresa_id"], gancho["id"], evento, 1 if ok else 0, codigo, erro, agora()),
        )
        return {"ok": ok, "codigo_http": codigo, "erro": erro}
