"""Servidor web do Sobrou+ (biblioteca padrão do Python — mesmo desenho do RMD Atendimento, sem dependências).

Telas:  /            app do consumidor (celular)
        /painel      painel das empresas parceiras e da equipe Sobrou+
        /entregador  app do entregador
API:    /api/...     JSON. Sessão em cookie HttpOnly (ou cabeçalho Authorization: Bearer).
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import socket
import sys
import threading
import time
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from sobrou import seguranca, manutencao  # noqa: E402
from sobrou.nucleo import ErroNegocio, NaoAutenticado  # noqa: E402
from sobrou.plataforma import Plataforma  # noqa: E402

ESTATICO = Path(__file__).resolve().parent / "static"
COOKIE = "sob_sessao"
LIMITE_CORPO = 6 * 1024 * 1024
ATRAS_DE_PROXY = os.getenv("SOBROU_ATRAS_DE_PROXY") == "1"
PAGINAS = {"/": "app.html", "/painel": "painel.html", "/rmd": "painel.html", "/entregador": "entregador.html", "/acesso": "acesso.html",
           "/termos": "termos.html", "/privacidade": "privacidade.html"}
# Um aplicativo instalável por perfil, cada um no SEU endereço (/apps/<nome>/), com nome, ícone e sessão próprios:
# instalar um no celular nunca troca o nome/ícone do outro, e entrar num não tira a pessoa do outro.
APPS = {
    "central": ("painel.html", "Sobrou+ Central", "Sobrou+ Central — equipe Sobrou+"),
    "loja": ("painel.html", "Sobrou+ Loja", "Sobrou+ Loja — administração da loja"),
    "caixa": ("painel.html", "Sobrou+ Caixa", "Sobrou+ Caixa — balcão da loja"),
    "entregador": ("entregador.html", "Sobrou+ Entrega", "Sobrou+ Entregador"),
    "cliente": ("app.html", "Sobrou+ Cliente", "Sobrou+ Cliente — ofertas e pedidos"),
}

_plataforma: Plataforma | None = None
_lock = threading.Lock()
limite_login = seguranca.LimiteChamadas(20)
limite_login_conta = seguranca.LimiteChamadas(12)
limite_cadastro = seguranca.LimiteChamadas(10)
limite_mutacoes = seguranca.LimiteChamadas(180)
limite_publico = seguranca.LimiteChamadas(60)  # telemetria, webhooks e demais rotas públicas


def plataforma() -> Plataforma:
    global _plataforma
    with _lock:
        if _plataforma is None:
            _plataforma = Plataforma(os.getenv("SOBROU_DADOS") or None)
        return _plataforma


ROTAS: list[tuple[str, re.Pattern, object, bool]] = []
limite_senha = seguranca.LimiteChamadas(8)
limite_2fa = seguranca.LimiteChamadas(8)


class Arquivo:
    """Resposta de download (CSV, backup, meus dados)."""
    def __init__(self, nome: str, dados: bytes, tipo: str):
        self.nome, self.dados, self.tipo = nome, dados, tipo


def rota(metodo: str, padrao: str, publica: bool = False):
    regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", padrao) + "$")

    def dec(f):
        ROTAS.append((metodo, regex, f, publica))
        return f
    return dec


def _recurso_rota(caminho: str) -> str | None:
    if caminho.startswith("/api/pedidos/"):
        if "/pagar" in caminho or "/pagamento" in caminho:
            return "pagamentos"
        if "/avaliar" in caminho:
            return "avaliacoes"
        return "pedidos"
    if caminho == "/api/pedidos":
        return "pedidos"
    if caminho.startswith("/api/pagamentos"):
        return "pagamentos"
    if caminho.startswith(("/api/avaliacoes", "/api/lojas/")):
        return "avaliacoes"
    if caminho.startswith(("/api/unidades",)):
        return "unidades"
    if caminho.startswith("/api/ofertas/") and "/estoque" in caminho:
        return "estoque"
    if caminho.startswith(("/api/ofertas", "/api/fotos")):
        return "ofertas"
    if caminho.startswith(("/api/dispatch", "/api/entregador")):
        return "entrega"
    if caminho.startswith(("/api/retirada",)):
        return "retirada"
    if caminho.startswith(("/api/graficos", "/api/relatorios")):
        return "relatorios"
    if caminho.startswith(("/api/financeiro", "/api/repasses", "/api/conciliacao")):
        return "financeiro"
    if caminho.startswith(("/api/doacoes", "/api/instituicoes")):
        return "doacoes"
    if caminho.startswith("/api/usuarios"):
        return "usuarios"
    return None


# ====================================================================== ROTAS PÚBLICAS
def _versao_telas() -> str:
    """Muda sempre que qualquer tela é publicada de novo: o app percebe e se atualiza sozinho."""
    import hashlib
    h = hashlib.sha1()
    for arq in sorted(ESTATICO.rglob("*")):
        if arq.is_file() and arq.suffix in (".html", ".js", ".css", ".webmanifest"):
            h.update(arq.read_bytes())
    return h.hexdigest()[:10]


VERSAO_TELAS = _versao_telas()


@rota("GET", "/api/saude", True)
def r_saude(h, p, a, q, c):
    return {"ok": True, "sistema": "sobrou+", "versao": f"{p.VERSAO}-{VERSAO_TELAS}"}


@rota("GET", "/api/config", True)
def r_config(h, p, a, q, c):
    cfg = p.config_plataforma()
    return {"tema": cfg["tema"], "nome": cfg["nome_exibicao"], "slogan": "Boa comida. Mais valor. Menos desperdício.",
            "logo": (ESTATICO / "img" / "logo.png").exists(), "url_acesso": h.url_acesso()}


@rota("GET", "/api/vitrine", True)
def r_vitrine(h, p, a, q, c):
    return {"itens": p.vitrine(q)}


@rota("GET", "/api/vitrine/{oid}", True)
def r_oferta_publica(h, p, a, q, c, oid):
    return p.oferta_publica(oid)


@rota("GET", "/api/impacto/publico", True)
def r_impacto_publico(h, p, a, q, c):
    i = p.impacto(None)
    return {k: i[k] for k in ("pedidos", "kg_desperdicio_evitado", "economia_clientes_centavos", "pessoas_beneficiadas", "instituicoes_atendidas")}


@rota("POST", "/api/entrar", True)
def r_entrar(h, p, a, q, c):
    chave_conta = h.ip() + ":" + str(c.get("email") or "").strip().lower()[:160]
    if not limite_login.permitir(h.ip()) or not limite_login_conta.permitir(chave_conta):
        raise ErroNegocio("Muitas tentativas. Aguarde um minuto.")
    s = p.entrar(c.get("email"), c.get("senha"), h.ip(), c.get("codigo"))
    h.cookie_novo = s["token"]
    return {"usuario": s["usuario"]}


@rota("POST", "/api/entrar-criador", True)
def r_entrar_criador(h, p, a, q, c):
    if not limite_login.permitir("criador:" + h.ip()):
        raise ErroNegocio("Muitas tentativas. Aguarde um minuto.")
    s = p.entrar_criador(c.get("senha"), h.ip(), c.get("codigo"))
    h.cookie_novo = s["token"]
    return {"usuario": s["usuario"]}


@rota("GET", "/api/convite/{tok}", True)
def r_ver_convite(h, p, a, q, c, tok):
    return p.ver_convite(tok)


@rota("POST", "/api/convite/{tok}", True)
def r_aceitar_convite(h, p, a, q, c, tok):
    if not limite_senha.permitir(h.ip()):
        raise ErroNegocio("Muitas tentativas. Aguarde um minuto.")
    s = p.aceitar_convite(tok, c.get("senha"), bool(c.get("aceite_termos")), h.ip())
    h.cookie_novo = s["token"]
    return {"usuario": s["usuario"]}


@rota("POST", "/api/sair", True)
def r_sair(h, p, a, q, c):
    p.sair(h.token() or "")
    h.cookie_novo = ""
    return {"ok": True}


@rota("POST", "/api/cadastro/cliente", True)
def r_cad_cliente(h, p, a, q, c):
    if not limite_cadastro.permitir(h.ip()):
        raise ErroNegocio("Muitos cadastros seguidos. Aguarde um minuto.")
    s = p.cadastrar_cliente(c, h.ip())
    h.cookie_novo = s["token"]
    return {"usuario": s["usuario"]}


@rota("POST", "/api/cadastro/empresa", True)
def r_cad_empresa(h, p, a, q, c):
    if not limite_cadastro.permitir(h.ip()):
        raise ErroNegocio("Muitos cadastros seguidos. Aguarde um minuto.")
    s = p.cadastrar_empresa(c, h.ip())
    h.cookie_novo = s["token"]
    return {"usuario": s["usuario"]}


@rota("POST", "/api/cadastro/instituicao", True)
def r_cad_inst(h, p, a, q, c):
    if not limite_cadastro.permitir(h.ip()):
        raise ErroNegocio("Muitos cadastros seguidos. Aguarde um minuto.")
    i = p.salvar_instituicao(None, c)
    return {"ok": True, "id": i["id"], "mensagem": "Recebemos o cadastro. A equipe Sobrou+ vai conferir e autorizar."}


@rota("POST", "/api/senha/esqueci", True)
def r_esqueci(h, p, a, q, c):
    if not limite_senha.permitir(h.ip()):
        raise ErroNegocio("Muitas tentativas. Aguarde um minuto.")
    return p.pedir_codigo_senha(c.get("email"))


@rota("POST", "/api/senha/codigo", True)
def r_senha_codigo(h, p, a, q, c):
    if not limite_senha.permitir(h.ip()):
        raise ErroNegocio("Muitas tentativas. Aguarde um minuto.")
    return p.redefinir_com_codigo(c.get("email"), c.get("codigo"), c.get("nova"))


@rota("GET", "/api/push/chave", True)
def r_push_chave(h, p, a, q, c):
    return {"chave": p.chave_push_publica()}


@rota("GET", "/api/lojas/{eid}/avaliacoes", True)
def r_aval_publicas(h, p, a, q, c, eid):
    if not p.recurso_habilitado(eid, "avaliacoes"):
        return {"itens": [], "nota": None}
    return {"itens": p.publico_avaliacoes(eid), "nota": p.notas_empresas().get(eid)}


# ====================================================================== CONTA
@rota("POST", "/api/push/inscrever")
def r_push_inscrever(h, p, a, q, c):
    return p.inscrever_push(a, c)


@rota("GET", "/api/meus-dados")
def r_meus_dados(h, p, a, q, c):
    return Arquivo("meus_dados_sobrou.json", json.dumps(p.meus_dados(a), ensure_ascii=False, indent=2).encode("utf-8"), "application/json")


@rota("POST", "/api/excluir-conta")
def r_excluir_conta(h, p, a, q, c):
    r = p.excluir_minha_conta(a, c.get("senha"))
    h.cookie_novo = ""
    return r


@rota("POST", "/api/pedidos/{pid}/avaliar")
def r_avaliar(h, p, a, q, c, pid):
    return p.avaliar_pedido(a, pid, c.get("nota"), c.get("comentario"))


@rota("GET", "/api/avaliacoes")
def r_avaliacoes(h, p, a, q, c):
    return p.listar_avaliacoes(a, q.get("empresa_id"))


@rota("POST", "/api/pedidos/{pid}/avaliar-cliente")
def r_avaliar_cliente(h, p, a, q, c, pid):
    return p.avaliar_cliente_pedido(a, pid, c.get("nota"), c.get("comentario"))


@rota("GET", "/api/avaliacoes-clientes")
def r_avaliacoes_clientes(h, p, a, q, c):
    return p.listar_avaliacoes_clientes(a, q.get("empresa_id"))


@rota("GET", "/api/minha-reputacao")
def r_minha_reputacao(h, p, a, q, c):
    return p.minha_reputacao(a)


@rota("POST", "/api/avaliacoes/{aid}/responder")
def r_responder_aval(h, p, a, q, c, aid):
    return p.responder_avaliacao(a, aid, c.get("resposta"))


@rota("GET", "/api/graficos")
def r_graficos(h, p, a, q, c):
    return p.graficos(a, q.get("empresa_id"), q.get("dias") or 14)


@rota("GET", "/api/relatorios/{tipo}")
def r_relatorio(h, p, a, q, c, tipo):
    nome, dados = p.relatorio_csv(a, tipo.replace(".csv", ""), q.get("empresa_id"), q.get("de"), q.get("ate"))
    return Arquivo(nome, dados, "text/csv; charset=utf-8")


@rota("GET", "/api/planos")
def r_planos(h, p, a, q, c):
    return {"itens": p.listar_planos(a)}


@rota("POST", "/api/planos")
def r_criar_plano(h, p, a, q, c):
    return p.salvar_plano(a, c)


@rota("PUT", "/api/planos/{plid}")
def r_editar_plano(h, p, a, q, c, plid):
    return p.salvar_plano(a, c, plid)


@rota("POST", "/api/empresas/{eid}/plano")
def r_definir_plano(h, p, a, q, c, eid):
    return p.definir_plano(a, eid, c.get("plano_id"))


@rota("GET", "/api/faturas")
def r_faturas(h, p, a, q, c):
    return {"itens": p.listar_faturas(a, q.get("empresa_id"))}


@rota("POST", "/api/faturas/{fid}/paga")
def r_fatura_paga(h, p, a, q, c, fid):
    return p.marcar_fatura_paga(a, fid, c.get("referencia"))


@rota("GET", "/api/sistema/backups")
def r_backups(h, p, a, q, c):
    return {"itens": p.listar_backups(a)}


@rota("POST", "/api/sistema/backups")
def r_fazer_backup(h, p, a, q, c):
    a.exigir("sistema", "ver")
    return {"nome": p.fazer_backup()}


@rota("GET", "/api/sistema/backups/{nome}")
def r_baixar_backup(h, p, a, q, c, nome):
    arq = p.arquivo_backup(a, nome)
    return Arquivo(arq.name, arq.read_bytes(), "application/octet-stream")


@rota("GET", "/api/eu")
def r_eu(h, p, a, q, c):
    u = p._usuario_publico(p.banco.um("SELECT * FROM usuarios WHERE id=?", (a.usuario_id,)))
    emp = p.obter_empresa(a, a.empresa_id) if a.empresa_id else None
    tema = (emp or {}).get("config", {}).get("tema") if emp else None
    if not tema or tema == "padrao":
        tema = p.config_plataforma()["tema"]
    eh_dono = a.usuario_id == p.id_dono()
    ck = SimpleCookie(h.headers.get("Cookie") or "")
    return {"usuario": u, "empresa": emp, "plataforma": a.plataforma, "tema": tema, "eh_dono": eh_dono,
            "senha_padrao": p.senha_padrao(a) if (eh_dono or a.plataforma) else False,
            "tem_2fa": bool(p.banco.um("SELECT totp_segredo FROM usuarios WHERE id=?", (a.usuario_id,))["totp_segredo"]),
            "conta_teste": p.eh_conta_teste(a.usuario_id), "pode_voltar_criador": "sob_criador" in ck,
            "avisos": p.listar_avisos(a, 1)["nao_lidos"],
            "permissoes": {r: [ac for ac in acs if a.pode(r, ac)] for r, acs in __import__("sobrou.nucleo", fromlist=["MATRIZ"]).MATRIZ.items()}}


@rota("POST", "/api/usuarios/{uid}/convite")
def r_novo_convite(h, p, a, q, c, uid):
    return p.novo_convite(a, uid)


def _dados_envio_convite(h, p, a, c, uid):
    a.exigir("usuarios", "editar")
    u = a.conferir_empresa(p.banco.um("SELECT * FROM usuarios WHERE id=?", (uid,)), "Usuário")
    token = str(c.get("token") or "").strip()
    if not token:
        raise ErroNegocio("Link de acesso ausente. Gere um novo link antes de enviar.")
    _convite, convidado = p._convite_valido(token)
    if convidado["id"] != uid:
        raise NaoAutenticado("Link de acesso inválido.")
    # Nunca reutilizar uma URL antiga enviada pelo navegador. O servidor é a fonte da URL atual.
    base = (h.url_acesso() or "").rstrip("/")
    if not base:
        raise ErroNegocio("Não foi possível determinar o endereço de acesso do Sobrou+.")
    caminho = f"/acesso?c={token}"
    link = base + caminho
    empresa = p.banco.um("SELECT nome FROM empresas WHERE id=?", (u["empresa_id"],)) if u.get("empresa_id") else None
    nome_empresa = f" ({empresa['nome']})" if empresa else ""
    papel_nome = __import__("sobrou.nucleo", fromlist=["PAPEIS"]).PAPEIS.get(u["papel"], "usuário")
    # O convite enviado pelo WhatsApp/e-mail deve conter somente o endereço clicável.
    # A tela do painel já mostra as instruções separadamente para o operador.
    mensagem = link
    return u, mensagem, link


@rota("POST", "/api/usuarios/{uid}/convite/whatsapp")
def r_enviar_convite_whatsapp(h, p, a, q, c, uid):
    u, mensagem, link = _dados_envio_convite(h, p, a, c, uid)
    from sobrou.integracoes import telefone_whatsapp
    from sobrou.rede import ErroRede
    cfg = p._wa()
    tel = telefone_whatsapp(u.get("telefone"))
    if not cfg:
        raise ErroNegocio("WhatsApp oficial não está configurado. O sistema vai abrir o WhatsApp Web com a mensagem pronta.")
    if not tel:
        raise ErroNegocio("Este usuário não tem celular com DDD cadastrado.")
    try:
        p._enviar_whatsapp(cfg, tel, mensagem)
    except ErroRede as e:
        detalhe = e.corpo.get("message") if isinstance(e.corpo, dict) else None
        raise ErroNegocio("O WhatsApp oficial não conseguiu enviar a mensagem." + (f" {detalhe}" if detalhe else "")) from e
    p.auditar(a, "usuario.convite_whatsapp", uid, empresa_id=u.get("empresa_id"))
    return {"ok": True, "mensagem": f"Link de acesso enviado por WhatsApp para {tel}.", "link": link}


@rota("POST", "/api/usuarios/{uid}/convite/email")
def r_enviar_convite_email(h, p, a, q, c, uid):
    u, mensagem, link = _dados_envio_convite(h, p, a, c, uid)
    if not p._email_cfg():
        raise ErroNegocio("SMTP de e-mail do Sobrou+ não está configurado. O sistema vai abrir seu aplicativo de e-mail com a mensagem pronta.")
    if not p.enviar_email(u["email"], "Seu acesso ao Sobrou+", mensagem):
        raise ErroNegocio("Não foi possível enviar o e-mail pelo SMTP configurado. Veja os erros em Sistema.")
    p.auditar(a, "usuario.convite_email", uid, empresa_id=u.get("empresa_id"))
    return {"ok": True, "mensagem": f"Link de acesso enviado para {u['email']}.", "link": link}


@rota("POST", "/api/seguranca/2fa/iniciar")
def r_2fa_iniciar(h, p, a, q, c):
    return p.iniciar_2fa(a)


@rota("POST", "/api/seguranca/2fa/confirmar")
def r_2fa_confirmar(h, p, a, q, c):
    if not limite_2fa.permitir(a.usuario_id + ":" + h.ip()):
        raise ErroNegocio("Muitas tentativas de confirmação. Aguarde um minuto.")
    return p.confirmar_2fa(a, c.get("codigo"))


@rota("POST", "/api/seguranca/2fa/desligar")
def r_2fa_desligar(h, p, a, q, c):
    return p.desligar_2fa(a, c.get("senha"))


@rota("GET", "/api/seguranca/sessoes")
def r_sessoes(h, p, a, q, c):
    return {"itens": p.sessoes_ativas(a)}


@rota("POST", "/api/seguranca/sair-todos")
def r_sair_todos(h, p, a, q, c):
    return p.sair_de_todos(a, h.token())


@rota("POST", "/api/criador/testar")
def r_criador_testar(h, p, a, q, c):
    return {"caminho": "/entrar?token=" + p.abrir_teste(a, c.get("perfil"))}


@rota("GET", "/api/rmd/testadores")
def r_testadores(h, p, a, q, c):
    return {**p.listar_testadores(a), "url_acesso": (h.url_acesso() or "").rstrip("/")}


@rota("POST", "/api/rmd/testadores")
def r_criar_testador(h, p, a, q, c):
    return {**p.criar_testador(a, c), "url_acesso": (h.url_acesso() or "").rstrip("/")}


@rota("POST", "/api/rmd/testadores/{tid}/links")
def r_links_testador(h, p, a, q, c, tid):
    return {**p.novos_links_testador(a, tid), "url_acesso": (h.url_acesso() or "").rstrip("/")}


@rota("POST", "/api/rmd/testadores/{tid}/ligar")
def r_ligar_testador(h, p, a, q, c, tid):
    return p.ligar_testador(a, tid, bool(c.get("ligado")))


@rota("POST", "/api/criador/voltar", True)
def r_criador_voltar(h, p, a, q, c):
    ck = SimpleCookie(h.headers.get("Cookie") or "")
    tok = ck["sob_criador"].value if "sob_criador" in ck else None
    ator = p.ator_da_sessao(tok, h.ip())
    if ator.usuario_id != p.id_dono() and ator.papel != "admin_sobrou":
        raise NaoAutenticado("Entre de novo como Desenvolvedor RMD.")
    h.cookie_novo = tok
    h.cookie_extra = ("sob_criador", "")
    return {"ok": True}


@rota("GET", "/api/financeiro/detalhado")
def r_fin_detalhado(h, p, a, q, c):
    return p.financeiro_detalhado(a, q.get("empresa_id"), q.get("de"), q.get("ate"), q.get("teste"))


@rota("POST", "/api/senha")
def r_senha(h, p, a, q, c):
    resultado = p.trocar_senha(a, c.get("atual"), c.get("nova"))
    # Revoga todas as outras sessões; a sessão atual permanece ativa.
    p.sair_de_todos(a, h.token() or "")
    return resultado


@rota("GET", "/api/avisos")
def r_avisos(h, p, a, q, c):
    return p.listar_avisos(a)


@rota("POST", "/api/avisos/lidos")
def r_avisos_lidos(h, p, a, q, c):
    return p.marcar_avisos_lidos(a)


# ====================================================================== CLIENTE
@rota("POST", "/api/cotar")
def r_cotar(h, p, a, q, c):
    m = p.cotar(a, c)
    m.pop("ofertas", None)
    return m


@rota("POST", "/api/pedidos")
def r_criar_pedido(h, p, a, q, c):
    return p.criar_pedido(a, c)


@rota("GET", "/api/pedidos")
def r_pedidos(h, p, a, q, c):
    return {"itens": p.listar_pedidos(a, q.get("empresa_id"), q.get("status"))}


@rota("GET", "/api/pedidos/{pid}")
def r_pedido(h, p, a, q, c, pid):
    return p.obter_pedido(a, pid)


@rota("POST", "/api/pedidos/{pid}/pagar")
def r_pagar(h, p, a, q, c, pid):
    return p.pagar(a, pid, c.get("meio", ""), h.base_url())


@rota("GET", "/api/pedidos/{pid}/pagamento")
def r_verificar_pag(h, p, a, q, c, pid):
    return p.verificar_pagamento(a, pid)


@rota("GET", "/api/meios-pagamento")
def r_meios(h, p, a, q, c):
    return p.meios_pagamento(a)


@rota("GET", "/api/pagamentos")
def r_pagamentos(h, p, a, q, c):
    return {"itens": p.listar_pagamentos(a, q.get("empresa_id"))}


@rota("POST", "/api/pagamentos/{pid}/cancelar")
def r_cancelar_pagamento(h, p, a, q, c, pid):
    return p.cancelar_pagamento(a, pid)


@rota("POST", "/api/pagamentos/{pid}/estornar")
def r_estornar_pagamento(h, p, a, q, c, pid):
    return p.estornar_pagamento(a, pid)


@rota("POST", "/api/webhooks/mercadopago", True)
def r_webhook_mp(h, p, a, q, c):
    cab = {k.lower(): v for k, v in h.headers.items()}
    resultado = p.webhook_mercadopago(q, c, cab)
    if not resultado.get("ok"):
        raise NaoAutenticado("Webhook rejeitado ou não confirmado pelo gateway.")
    return resultado


@rota("POST", "/api/telemetria", True)
def r_telemetria(h, p, a, q, c):
    return p.registrar_evento_uso(c)


@rota("GET", "/api/marketing")
def r_marketing(h, p, a, q, c):
    return p.relatorio_marketing(a, q.get("empresa_id"), q.get("dias", 30))


@rota("GET", "/api/mapa/rota")
def r_mapa_rota(h, p, a, q, c):
    try:
        la1, ln1 = (float(x) for x in q.get("de", "").split(","))
        la2, ln2 = (float(x) for x in q.get("para", "").split(","))
    except ValueError as e:
        raise ErroNegocio("Coordenadas inválidas.") from e
    return p.rota(la1, ln1, la2, ln2, com_linha=True) or {}


@rota("GET", "/api/mapa/buscar")
def r_mapa_buscar(h, p, a, q, c):
    return {"itens": p.buscar_endereco(a, q.get("q"))}


@rota("GET", "/api/integracoes")
def r_integracoes(h, p, a, q, c):
    return {**p.integracoes_publicas(a), "mensagens": p.resumo_mensagens(a), "url_webhook": h.base_url() + "/api/webhooks/mercadopago"}


@rota("PUT", "/api/integracoes/{nome}")
def r_salvar_integracao(h, p, a, q, c, nome):
    return p.salvar_integracao(a, nome, c)


@rota("POST", "/api/integracoes/{nome}/testar")
def r_testar_integracao(h, p, a, q, c, nome):
    return p.testar_integracao(a, nome, c)


@rota("POST", "/api/pedidos/{pid}/cancelar")
def r_cancelar(h, p, a, q, c, pid):
    return p.cancelar_pedido(a, pid, c.get("motivo"))


@rota("POST", "/api/pedidos/{pid}/confirmar")
def r_confirmar(h, p, a, q, c, pid):
    return p.confirmar_recebimento(a, pid)


@rota("POST", "/api/pedidos/{pid}/avancar")
def r_avancar(h, p, a, q, c, pid):
    return p.avancar_pedido(a, pid, c.get("acao"))


@rota("POST", "/api/retirada")
def r_retirada(h, p, a, q, c):
    return p.validar_retirada(a, c.get("codigo"), c.get("empresa_id"))


@rota("GET", "/api/meu-impacto")
def r_meu_impacto(h, p, a, q, c):
    return p.impacto(cliente_id=a.usuario_id)


@rota("GET", "/api/favoritos")
def r_favoritos(h, p, a, q, c):
    return {"empresas": p.listar_favoritos(a)}


@rota("POST", "/api/favoritos/{eid}")
def r_favorito(h, p, a, q, c, eid):
    return p.alternar_favorito(a, eid)


# ====================================================================== EMPRESAS E UNIDADES
@rota("GET", "/api/empresas")
def r_empresas(h, p, a, q, c):
    return {"itens": p.listar_empresas(a)}


@rota("POST", "/api/empresas")
def r_criar_empresa(h, p, a, q, c):
    return p.criar_empresa(a, c)


@rota("GET", "/api/empresas/{eid}")
def r_empresa(h, p, a, q, c, eid):
    return p.obter_empresa(a, eid)


@rota("PUT", "/api/empresas/{eid}")
def r_editar_empresa(h, p, a, q, c, eid):
    return p.editar_empresa(a, eid, c)


@rota("POST", "/api/empresas/{eid}/aprovar")
def r_aprovar(h, p, a, q, c, eid):
    return p.aprovar_empresa(a, eid, bool(c.get("aprovada", True)), c.get("ativa"))


@rota("GET", "/api/unidades")
def r_unidades(h, p, a, q, c):
    return {"itens": p.listar_unidades(a, q.get("empresa_id"))}


@rota("POST", "/api/unidades")
def r_criar_unidade(h, p, a, q, c):
    return p.salvar_unidade(a, c)


@rota("PUT", "/api/unidades/{uid}")
def r_editar_unidade(h, p, a, q, c, uid):
    return p.salvar_unidade(a, c, uid)


# ====================================================================== OFERTAS, FOTOS, ESTOQUE, PREÇO
@rota("POST", "/api/fotos")
def r_foto(h, p, a, q, c):
    return p.enviar_foto(a, c)


@rota("GET", "/api/ofertas")
def r_ofertas(h, p, a, q, c):
    return {"itens": p.listar_ofertas(a, q.get("empresa_id"), q.get("status"))}


@rota("POST", "/api/ofertas")
def r_criar_oferta(h, p, a, q, c):
    return p.salvar_oferta(a, c)


@rota("GET", "/api/ofertas/{oid}")
def r_oferta(h, p, a, q, c, oid):
    return p.obter_oferta(a, oid)


@rota("PUT", "/api/ofertas/{oid}")
def r_editar_oferta(h, p, a, q, c, oid):
    return p.salvar_oferta(a, c, oid)


@rota("POST", "/api/ofertas/{oid}/status")
def r_status_oferta(h, p, a, q, c, oid):
    return p.mudar_status_oferta(a, oid, c.get("status"))


@rota("POST", "/api/ofertas/{oid}/estoque")
def r_estoque(h, p, a, q, c, oid):
    return p.ajustar_estoque(a, oid, c.get("delta"), c.get("motivo"))


@rota("POST", "/api/ofertas/{oid}/preco")
def r_preco(h, p, a, q, c, oid):
    return p.alterar_preco(a, oid, c.get("preco"))


# ====================================================================== LOGÍSTICA
@rota("GET", "/api/dispatch")
def r_dispatch(h, p, a, q, c):
    return p.painel_dispatch(a, q.get("empresa_id"))


@rota("POST", "/api/dispatch/{enid}/buscar")
def r_buscar_entregador(h, p, a, q, c, enid):
    return p.buscar_entregador_novamente(a, enid)


@rota("POST", "/api/dispatch/{enid}/designar")
def r_designar(h, p, a, q, c, enid):
    return p.designar_manual(a, enid, c.get("entregador_id"))


@rota("GET", "/api/entregador")
def r_entregador(h, p, a, q, c):
    return p.painel_entregador(a)


@rota("POST", "/api/entregador/online")
def r_online(h, p, a, q, c):
    return p.ficar_online(a, bool(c.get("online")))


@rota("POST", "/api/entregador/posicao")
def r_posicao(h, p, a, q, c):
    return p.enviar_posicao(a, c.get("lat"), c.get("lng"), c.get("precisao"))


@rota("POST", "/api/entregador/corridas/{enid}/responder")
def r_responder(h, p, a, q, c, enid):
    return p.responder_corrida(a, enid, bool(c.get("aceitar")))


@rota("POST", "/api/entregador/corridas/{enid}/problema")
def r_problema_entrega(h, p, a, q, c, enid):
    return p.reportar_problema_entrega(a, enid, c.get("tipo"), c.get("descricao", ""))


@rota("POST", "/api/entregador/corridas/{enid}/avancar")
def r_corrida(h, p, a, q, c, enid):
    return p.avancar_corrida(a, enid, c.get("acao"), c.get("codigo"))


# ====================================================================== FINANCEIRO
@rota("GET", "/api/financeiro")
def r_fin(h, p, a, q, c):
    return p.resumo_financeiro(a, q.get("empresa_id"), q.get("de"), q.get("ate"))


@rota("GET", "/api/repasses")
def r_repasses(h, p, a, q, c):
    return {"itens": p.listar_repasses(a, q.get("empresa_id"))}


@rota("POST", "/api/repasses")
def r_calc_repasse(h, p, a, q, c):
    return p.calcular_repasse(a, c.get("empresa_id"), c.get("de"), c.get("ate"))


@rota("POST", "/api/repasses/{rid}/pago")
def r_repasse_pago(h, p, a, q, c, rid):
    return p.marcar_repasse_pago(a, rid, c.get("referencia"))


@rota("GET", "/api/conciliacao")
def r_conciliacao(h, p, a, q, c):
    return p.conciliacao(a, q.get("empresa_id"))


# ====================================================================== DOAÇÕES, INSTITUIÇÕES, IMPACTO
@rota("GET", "/api/doacoes")
def r_doacoes(h, p, a, q, c):
    return {"itens": p.listar_doacoes(a, q.get("empresa_id"))}


@rota("POST", "/api/doacoes")
def r_propor(h, p, a, q, c):
    return p.propor_doacao(a, c)


@rota("POST", "/api/doacoes/{did}/{acao}")
def r_doacao_acao(h, p, a, q, c, did, acao):
    return p.avancar_doacao(a, did, acao, c)


@rota("GET", "/api/instituicoes")
def r_insts(h, p, a, q, c):
    return {"itens": p.listar_instituicoes(a, q.get("autorizadas") == "1")}


@rota("POST", "/api/instituicoes")
def r_criar_inst(h, p, a, q, c):
    return p.salvar_instituicao(a, c)


@rota("PUT", "/api/instituicoes/{iid}")
def r_editar_inst(h, p, a, q, c, iid):
    return p.salvar_instituicao(a, c, iid)


@rota("POST", "/api/instituicoes/{iid}/autorizar")
def r_autorizar(h, p, a, q, c, iid):
    return p.autorizar_instituicao(a, iid, bool(c.get("autorizada", True)))


@rota("GET", "/api/impacto")
def r_impacto(h, p, a, q, c):
    return p.impacto(a, q.get("empresa_id"))


# ====================================================================== GESTÃO
@rota("GET", "/api/usuarios")
def r_usuarios(h, p, a, q, c):
    return {"itens": p.listar_usuarios(a, q.get("empresa_id"))}


@rota("POST", "/api/usuarios")
def r_criar_usuario(h, p, a, q, c):
    return p.criar_usuario(a, c)


@rota("POST", "/api/usuarios/{uid}/ativo")
def r_ativo(h, p, a, q, c, uid):
    return p.ativar_usuario(a, uid, bool(c.get("ativo")))


@rota("POST", "/api/usuarios/{uid}/redefinir")
def r_redefinir(h, p, a, q, c, uid):
    return p.redefinir_senha(a, uid)


@rota("GET", "/api/auditoria")
def r_auditoria(h, p, a, q, c):
    return {"itens": p.listar_auditoria(a, q.get("empresa_id"))}


@rota("GET", "/api/config-plataforma")
def r_cfg_plat(h, p, a, q, c):
    a.exigir("sistema", "ver")
    return p.config_plataforma()


@rota("PUT", "/api/config-plataforma")
def r_salvar_cfg_plat(h, p, a, q, c):
    return p.salvar_config_plataforma(a, c)


@rota("GET", "/api/sistema")
def r_sistema(h, p, a, q, c):
    return p.painel_sistema(a)


@rota("GET", "/api/seguranca/painel")
def r_painel_seguranca(h, p, a, q, c):
    # O método no núcleo repete a validação pelo ID do proprietário RMD.
    return p.painel_seguranca(a)


@rota("GET", "/api/manutencao/painel")
def r_manutencao_painel(h, p, a, q, c):
    if a.usuario_id != p.id_dono():
        raise NaoAutenticado("Área exclusiva do desenvolvedor RMD.")
    status = manutencao.rotina_inicial()
    backups = sorted(manutencao.BACKUPS.glob("sobrou-*.db"), key=lambda x: x.stat().st_mtime, reverse=True)
    ultimo = backups[0] if backups else None
    return {
        "ambiente": os.getenv("SOBROU_AMBIENTE", "producao"),
        "dados": str(manutencao.DADOS),
        "porta": os.getenv("SOBROU_PORTA", "8095"),
        "producao_separada": (os.getenv("SOBROU_AMBIENTE", "producao") == "producao"),
        "desenvolvimento_dados": str(RAIZ / "data_desenvolvimento"),
        "backup": status.get("backup", {}),
        "integridade": status.get("integridade", {}),
        "retencao": status.get("retencao", {}),
        "ultimo_backup": ultimo.name if ultimo else None,
    }


@rota("POST", "/api/manutencao/backup")
def r_manutencao_backup(h, p, a, q, c):
    if a.usuario_id != p.id_dono():
        raise NaoAutenticado("Área exclusiva do desenvolvedor RMD.")
    return manutencao.backup_e_teste()


@rota("POST", "/api/manutencao/integridade")
def r_manutencao_integridade(h, p, a, q, c):
    if a.usuario_id != p.id_dono():
        raise NaoAutenticado("Área exclusiva do desenvolvedor RMD.")
    return manutencao.verificar_integridade()


@rota("GET", "/api/recursos")
def r_recursos(h, p, a, q, c):
    if a.plataforma:
        return p.recursos_plataforma(a)
    if a.empresa_id:
        return p.recursos_empresa(a, a.empresa_id)
    raise ErroNegocio("Esta conta não pertence a uma empresa.")


@rota("PUT", "/api/recursos")
def r_salvar_recursos(h, p, a, q, c):
    return p.salvar_recursos_plataforma(a, c)


@rota("GET", "/api/empresas/{eid}/recursos")
def r_recursos_empresa(h, p, a, q, c, eid):
    return p.recursos_empresa(a, eid)


@rota("PUT", "/api/empresas/{eid}/recursos")
def r_salvar_recursos_empresa(h, p, a, q, c, eid):
    return p.salvar_recursos_empresa(a, eid, c)


# ====================================================================== SERVIDOR
class Handler(BaseHTTPRequestHandler):
    server_version = "SobrouPlus"
    sys_version = ""
    timeout = 30  # conexão parada/lenta é encerrada (não prende o servidor)
    cookie_novo: str | None = None
    cookie_extra: tuple | None = None
    app: str | None = None  # aplicativo instalável em uso (/apps/<nome>/), ou None

    def log_message(self, fmt, *args):  # noqa: D401 - log curto
        if os.getenv("SOBROU_LOG"):
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _proxy_confiavel(self) -> bool:
        if not ATRAS_DE_PROXY:
            return False
        # Railway e serviços parecidos: o proxy da hospedagem não vem de 127.0.0.1.
        return self.client_address[0] in ("127.0.0.1", "::1") or os.getenv("SOBROU_PROXY_HOSPEDAGEM") == "1"

    def ip(self) -> str:
        if self._proxy_confiavel():
            # O ÚLTIMO endereço é o que o próprio túnel/proxy anotou; os anteriores
            # podem ter sido escritos por quem está acessando (e burlar o limite de tentativas).
            encaminhado = (self.headers.get("X-Forwarded-For") or "").split(",")[-1].strip()
            if encaminhado:
                return encaminhado[:64]
        return self.client_address[0]

    def https(self) -> bool:
        return self._proxy_confiavel() and self.headers.get("X-Forwarded-Proto") == "https"

    def base_url(self) -> str:
        encaminhado = self.headers.get("X-Forwarded-Host") if self._proxy_confiavel() else None
        host = (encaminhado or self.headers.get("Host") or "").split(",")[0].strip()
        return f"{'https' if self.https() else 'http'}://{host}{self.prefixo()}" if host else ""

    def url_acesso(self) -> str:
        """URL que outra pessoa consegue abrir; em modo local troca loopback pelo IP da rede."""
        configurada = (os.getenv("SOBROU_URL_PUBLICA") or "").strip().rstrip("/")
        if configurada:
            return configurada
        base = self.base_url()
        if not base:
            return ""
        if self._proxy_confiavel():
            return base
        host = (self.headers.get("Host") or "").split(",")[0].strip()
        host_sem_porta = host
        porta = ""
        if host.startswith("["):
            fim = host.find("]")
            host_sem_porta = host[1:fim] if fim > 0 else host
            if fim > 0 and len(host) > fim + 1 and host[fim + 1] == ":":
                porta = host[fim + 2:]
        elif ":" in host:
            host_sem_porta, porta = host.rsplit(":", 1)
        if host_sem_porta in ("127.0.0.1", "localhost", "::1"):
            ip = None
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
            except OSError:
                pass
            finally:
                s.close()
            if ip:
                scheme = "https" if self.https() else "http"
                suffixo = f":{porta}" if porta else ""
                return f"{scheme}://{ip}{suffixo}{self.prefixo()}"
        return base

    def prefixo(self) -> str:
        """Caminho na frente quando o Sobrou+ é servido dentro de outro endereço (ex.: /sobrou)."""
        pre = (self.headers.get("X-Forwarded-Prefix") or "").rstrip("/") if self._proxy_confiavel() else ""
        return pre if re.fullmatch(r"(/[a-z0-9-]+)?", pre) else ""

    def prefixo_app(self) -> str:
        """Prefixo + aplicativo (ex.: /sobrou/apps/caixa): para onde o usuário volta sem sair do app instalado."""
        return self.prefixo() + (f"/apps/{self.app}" if self.app else "")

    def caminho_cookie(self) -> str:
        """O cookie de sessão só vale dentro do Sobrou+ (não vaza para outro sistema servido no mesmo endereço).
        Em cada aplicativo instalado vale só dentro dele: Caixa e Loja no mesmo celular ficam com sessões separadas."""
        return self.prefixo_app() or "/"

    def nome_cookie(self) -> str:
        return COOKIE + (f"_{self.app}" if self.app else "")

    def token(self) -> str | None:
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        # o navegador manda primeiro o cookie do caminho mais específico (/sobrou): vale o primeiro
        for parte in (self.headers.get("Cookie") or "").split(";"):
            nome, _, valor = parte.strip().partition("=")
            if nome == self.nome_cookie() and valor:
                return valor
        return None

    def _seguranca(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")  # o mapa (OpenStreetMap) exige saber o site; só vai o endereço, nunca a página
        self.send_header("Permissions-Policy", "geolocation=(self), camera=(self)")
        if self.https():
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data: blob: https://tile.openstreetmap.org https://*.tile.openstreetmap.org; style-src 'self' 'unsafe-inline'; script-src 'self'; "
                         "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

    def _json(self, status: int, dados):
        corpo = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        if self.cookie_novo is not None:
            seguro = "; Secure" if self.https() else ""
            if self.cookie_novo:
                self.send_header("Set-Cookie", f"{self.nome_cookie()}={self.cookie_novo}; Path={self.caminho_cookie()}; HttpOnly; SameSite=Lax; Max-Age={seguranca.DURACAO_SESSAO_HORAS * 3600}{seguro}")
            else:
                self.send_header("Set-Cookie", f"{self.nome_cookie()}=; Path={self.caminho_cookie()}; HttpOnly; SameSite=Lax; Max-Age=0{seguro}")
                if self.caminho_cookie() != "/" and not self.app:  # apaga também o cookie antigo (versões anteriores usavam Path=/)
                    self.send_header("Set-Cookie", f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{seguro}")
        if self.cookie_extra is not None:
            seguro = "; Secure" if self.https() else ""
            nome, valor = self.cookie_extra
            idade = seguranca.DURACAO_SESSAO_HORAS * 3600 if valor else 0
            self.send_header("Set-Cookie", f"{nome}={valor}; Path={self.caminho_cookie()}; HttpOnly; SameSite=Lax; Max-Age={idade}{seguro}")
        self._seguranca()
        self.end_headers()
        self.wfile.write(corpo)

    def _arquivo(self, caminho: Path, tipo: str | None = None, cache: str = "no-cache"):
        dados = caminho.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo or mimetypes.guess_type(caminho.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", cache)
        self._seguranca()
        self.end_headers()
        self.wfile.write(dados)

    def _enviar_bytes(self, dados: bytes, tipo: str):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-cache")
        self._seguranca()
        self.end_headers()
        self.wfile.write(dados)

    def _pagina_app(self, pagina: str):
        """A mesma tela, com o nome e o ícone do aplicativo (o iPhone usa estes dados ao adicionar à Tela de Início)."""
        _pag, curto, titulo = APPS[self.app]
        html = (ESTATICO / pagina).read_text(encoding="utf-8")
        html = re.sub(r"<title>.*?</title>", f"<title>{titulo}</title>", html, count=1, flags=re.S)
        html = html.replace('href="static/img/icone-192.png"', f'href="static/img/apps/{self.app}-180.png"')
        html = html.replace('href="static/img/favicon.png"', f'href="static/img/apps/{self.app}-192.png"')
        html = html.replace("</head>", f'<meta name="apple-mobile-web-app-title" content="{curto}">\n'
                                       f'<meta name="application-name" content="{curto}">\n'
                                       '<meta name="apple-mobile-web-app-capable" content="yes">\n'
                                       '<meta name="mobile-web-app-capable" content="yes">\n</head>', 1)
        return self._enviar_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    def _manifesto_app(self):
        _pag, curto, titulo = APPS[self.app]
        base = json.loads((ESTATICO / "manifest.webmanifest").read_text(encoding="utf-8"))
        icones = f"static/img/apps/{self.app}"
        m = {
            # id próprio = aplicativo próprio no celular (não substitui o outro na instalação)
            "id": f"{self.prefixo()}/apps/{self.app}/", "name": titulo, "short_name": curto,
            "description": base.get("description"), "start_url": "./", "scope": "./", "display": "standalone",
            "orientation": "portrait", "background_color": base.get("background_color"), "theme_color": base.get("theme_color"),
            "lang": "pt-BR",
            "icons": [{"src": f"{icones}-192.png", "sizes": "192x192", "type": "image/png"},
                      {"src": f"{icones}-512.png", "sizes": "512x512", "type": "image/png"},
                      {"src": f"{icones}-512-mascara.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
        }
        return self._enviar_bytes(json.dumps(m, ensure_ascii=False, indent=1).encode("utf-8"), "application/manifest+json")

    def _baixar(self, arq: "Arquivo"):
        self.send_response(200)
        self.send_header("Content-Type", arq.tipo)
        self.send_header("Content-Length", str(len(arq.dados)))
        self.send_header("Content-Disposition", f'attachment; filename="{arq.nome}"')
        self.send_header("Cache-Control", "no-store")
        self._seguranca()
        self.end_headers()
        self.wfile.write(arq.dados)

    def _erro_simples(self, status: int, texto: str):
        corpo = texto.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self._seguranca()
        self.end_headers()
        self.wfile.write(corpo)

    def _origem_segura(self) -> bool:
        """Impede requisições de outro site quando a sessão vem do cookie."""
        if self.headers.get("Authorization"):
            return True
        if not self.headers.get("Cookie"):
            return True
        origem = (self.headers.get("Origin") or "").strip()
        if not origem:
            referer = (self.headers.get("Referer") or "").strip()
            if referer:
                origem = referer
        if not origem:
            # Clientes nativos podem não enviar Origin/Referer; JSON-only já
            # impede formulários cross-site simples.
            return True
        try:
            u = urlparse(origem)
            host = (self.headers.get("X-Forwarded-Host") if self._proxy_confiavel() else None) or self.headers.get("Host") or ""
            host = (host or "").split(",")[0].strip()
            esquema = "https" if self.https() else "http"
            return u.scheme == esquema and u.netloc == host
        except ValueError:
            return False

    def do_GET(self):  # noqa: N802
        self._tratar("GET")

    def do_POST(self):  # noqa: N802
        self._tratar("POST")

    def do_PUT(self):  # noqa: N802
        self._tratar("PUT")

    def _tratar(self, metodo: str):
        self.cookie_novo = None
        self.cookie_extra = None
        self.app = None
        url = urlparse(self.path)
        caminho_original = url.path or "/"
        m_app = re.match(r"^/apps/([a-z]+)(/.*)?$", caminho_original)
        if m_app and m_app.group(1) in APPS:
            self.app = m_app.group(1)
            if not m_app.group(2):  # /apps/caixa -> /apps/caixa/ (os arquivos relativos ficam dentro do app)
                self.send_response(302)
                self.send_header("Location", self.prefixo_app() + "/" + (("?" + url.query) if url.query else ""))
                self.send_header("Content-Length", "0")
                self._seguranca()
                self.end_headers()
                return
            caminho_original = m_app.group(2)
        caminho = caminho_original.rstrip("/") or "/"
        p = plataforma()
        try:
            # As páginas usam recursos relativos (static/...). Com barra final,
            # o navegador procura /painel/static/... e /rmd/static/..., que não existem.
            # Redirecionamos para a URL canônica sem barra, preservando prefixo e query.
            if metodo == "GET" and not caminho.startswith("/api/") and caminho_original != "/" and caminho_original.endswith("/") and caminho in PAGINAS:
                destino = self.prefixo_app() + caminho + (("?" + url.query) if url.query else "")
                self.send_response(302)
                self.send_header("Location", destino)
                self.send_header("Cache-Control", "no-store")
                self._seguranca()
                self.end_headers()
                return None
            if metodo == "GET" and not caminho.startswith("/api/"):
                return self._estatico(p, caminho, url)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            for m, regex, f, publica in ROTAS:
                if m != metodo:
                    continue
                achou = regex.match(caminho)
                if not achou:
                    continue
                if metodo in ("POST", "PUT"):
                    if not self._origem_segura():
                        return self._json(403, {"erro": "Origem da requisição não autorizada."})
                    limite = limite_publico if publica else limite_mutacoes
                    if not limite.permitir(self.ip() + ":" + caminho[:180]):
                        return self._json(429, {"erro": "Muitas alterações em sequência. Aguarde um minuto."})
                corpo = {}
                if metodo in ("POST", "PUT"):
                    # só JSON: bloqueia formulário de outro site (CSRF) mesmo com o cookie
                    if "application/json" not in (self.headers.get("Content-Type") or ""):
                        return self._json(415, {"erro": "Envie JSON."})
                    try:
                        tam = int(self.headers.get("Content-Length") or 0)
                    except ValueError:
                        tam = -1
                    if tam < 0:
                        return self._json(400, {"erro": "Tamanho do envio inválido."})
                    if tam > LIMITE_CORPO:
                        return self._json(413, {"erro": "Envio grande demais."})
                    bruto = self.rfile.read(tam) if tam else b"{}"
                    try:
                        corpo = json.loads(bruto or b"{}")
                    except ValueError:
                        return self._json(400, {"erro": "JSON inválido."})
                    if not isinstance(corpo, dict):
                        return self._json(400, {"erro": "JSON inválido."})
                ator = None if publica else p.ator_da_sessao(self.token(), self.ip())
                if ator is not None and ator.extras.get("trocar_senha") and caminho not in ("/api/eu", "/api/senha", "/api/avisos"):
                    return self._json(403, {"erro": "Troque a senha inicial antes de continuar.", "trocar_senha": True})
                # 2FA temporariamente opcional/desativado no fluxo de entrada.
                # A infraestrutura de TOTP permanece disponível para reativação futura,
                # mas nenhuma tela/API exige configuração ou código para acessar o painel.
                recurso = _recurso_rota(caminho)
                if ator is not None and ator.papel == "cliente" and metodo == "GET" and caminho.startswith("/api/pedidos"):
                    recurso = None  # clientes continuam acompanhando pedidos já existentes se novas vendas forem pausadas
                if ator is not None and recurso and not ator.plataforma:
                    empresa_recurso = ator.empresa_id
                    if not empresa_recurso and ator.papel == "cliente":
                        pedido_match = re.match(r"^/api/pedidos/([^/]+)", caminho)
                        if pedido_match:
                            pr = p.banco.um("SELECT empresa_id FROM pedidos WHERE id=?", (pedido_match.group(1),))
                            empresa_recurso = pr["empresa_id"] if pr else None
                    bloqueado = (empresa_recurso and not p.recurso_habilitado(empresa_recurso, recurso))
                    if not empresa_recurso and ator.papel == "instituicao" and not p._recurso_global(recurso):
                        bloqueado = True
                    if bloqueado:
                        return self._json(403, {"erro": "Este recurso está desativado para esta conta. Fale com o suporte Sobrou+.", "recurso": recurso})
                resultado = f(self, p, ator, q, corpo, **achou.groupdict())
                if isinstance(resultado, Arquivo):
                    return self._baixar(resultado)
                return self._json(200, resultado)
            return self._json(404, {"erro": "Endereço não encontrado."})
        except NaoAutenticado as e:
            from sobrou.acesso import PrecisaCodigo
            if isinstance(e, PrecisaCodigo):
                return self._json(401, {"erro": str(e), "precisa_codigo": True})
            if self.token() and caminho not in ("/api/entrar", "/api/entrar-criador"):
                self.cookie_novo = ""
            return self._json(401, {"erro": str(e)})
        except ErroNegocio as e:
            return self._json(e.status, {"erro": str(e)})
        except Exception as e:  # noqa: BLE001
            p.registrar_erro(caminho, metodo, e)
            traceback.print_exc()
            return self._json(500, {"erro": "Erro interno. O erro foi registrado para a equipe Sobrou+."})

    def _estatico(self, p: Plataforma, caminho: str, url):
        if caminho == "/entrar":
            token = (parse_qs(url.query).get("token") or [""])[0]
            try:
                s = p.entrar_com_token_unico(token, self.ip())
            except ErroNegocio:
                return self._erro_simples(403, "Link de entrada inválido ou vencido.")
            destino = {"cliente": "/", "entregador": "/entregador"}.get(s["usuario"]["papel"], "/painel")
            seguro = "; Secure" if self.https() else ""
            self.send_response(302)
            self.send_header("Location", self.prefixo_app() + destino)
            atual = self.token()
            if atual and p.eh_conta_teste(s["usuario"]["id"]):
                try:
                    quem = p.ator_da_sessao(atual)
                    if quem.usuario_id == p.id_dono() or quem.papel == "admin_sobrou":
                        self.send_header("Set-Cookie", f"sob_criador={atual}; Path={self.caminho_cookie()}; HttpOnly; SameSite=Lax; Max-Age={seguranca.DURACAO_SESSAO_HORAS * 3600}{seguro}")
                except ErroNegocio:
                    pass
            self.send_header("Set-Cookie", f"{self.nome_cookie()}={s['token']}; Path={self.caminho_cookie()}; HttpOnly; SameSite=Lax; Max-Age={seguranca.DURACAO_SESSAO_HORAS * 3600}{seguro}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        m = re.match(r"^/fotos/([0-9a-f]{20})(/mini)?$", caminho)
        if m:
            try:
                arq, tipo = p.arquivo_foto(m.group(1), bool(m.group(2)))
            except ErroNegocio:
                return self._erro_simples(404, "Foto não encontrada.")
            return self._arquivo(arq, tipo, "public, max-age=86400")
        if self.app and caminho == "/":
            return self._pagina_app(APPS[self.app][0])
        if caminho in PAGINAS:
            if self.app:
                return self._pagina_app(PAGINAS[caminho])
            return self._arquivo(ESTATICO / PAGINAS[caminho], "text/html; charset=utf-8")
        if caminho == "/sw.js":  # na raiz do app para valer em todas as telas
            return self._arquivo(ESTATICO / "sw.js", "text/javascript; charset=utf-8")
        if caminho == "/manifest.webmanifest":
            if self.app:
                return self._manifesto_app()
            return self._arquivo(ESTATICO / "manifest.webmanifest", "application/manifest+json")
        if caminho.startswith("/static/"):
            alvo = (ESTATICO / caminho[len("/static/"):]).resolve()
            if ESTATICO.resolve() in alvo.parents and alvo.is_file():
                return self._arquivo(alvo)
        return self._erro_simples(404, "Página não encontrada.")


def _rotina_em_segundo_plano(parar: threading.Event):
    while not parar.wait(30):
        try:
            if os.getenv("SOBROU_DEMO") == "1":
                from sobrou import demo
                demo._renovar_ofertas(plataforma())
            plataforma().rotina()
        except Exception as e:  # noqa: BLE001
            plataforma().registrar_erro("rotina", "-", e)


def criar_servidor(host: str = "127.0.0.1", porta: int = 8095) -> ThreadingHTTPServer:
    if os.getenv("SOBROU_PUBLICO") == "1" and os.getenv("SOBROU_HTTPS") != "1":
        raise RuntimeError("Publicação externa bloqueada: configure HTTPS no proxy e defina SOBROU_HTTPS=1.")
    servidor = ThreadingHTTPServer((host, porta), Handler)
    servidor.daemon_threads = True
    parar = threading.Event()
    threading.Thread(target=_rotina_em_segundo_plano, args=(parar,), daemon=True, name="SobrouRotina").start()
    servidor.parar_rotina = parar
    return servidor


if __name__ == "__main__":
    host = os.getenv("SOBROU_HOST", "127.0.0.1")
    porta = int(os.getenv("PORT", os.getenv("SOBROU_PORTA", "8095")))
    p = plataforma()
    if os.getenv("SOBROU_DONO"):
        p.definir_dono(os.getenv("SOBROU_DONO"))
    if os.getenv("SOBROU_DEMO") == "1":  # versão de testes na internet: dados fictícios marcados como demonstração
        from sobrou import demo
        demo.garantir_demonstracao(p)
    p.garantir_planos()
    p.rotina()
    print(f"[Sobrou+] http://{host}:{porta}", flush=True)
    criar_servidor(host, porta).serve_forever()
