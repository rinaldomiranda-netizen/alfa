"""Contas: login, sessões, usuários, empresas parceiras, unidades, instituições, configuração, auditoria e avisos."""
from __future__ import annotations

import json
from datetime import timedelta

from . import seguranca
from .nucleo import (PAPEIS, PAPEIS_EMPRESA, Ator, ErroNegocio, NaoAutenticado, NaoEncontrado, SemPermissao, iso,
                     novo_id, real, slugificar, texto)

TIPOS_EMPRESA = ("restaurante", "lanchonete", "padaria", "mercado", "supermercado", "hortifruti", "cafe",
                 "confeitaria", "outra")
TEMAS = ("claro", "medio", "escuro")
TAXA_PADRAO = 12.0  # % da taxa Sobrou+ sobre o valor dos produtos (configurável por empresa)


def _email(valor) -> str:
    e = (texto(valor, 160, True, "o e-mail") or "").lower()
    if "@" not in e or "." not in e.split("@")[-1]:
        raise ErroNegocio("E-mail inválido.")
    return e


class ContasMixin:
    # ================================================================ AUDITORIA E AVISOS
    def auditar(self, ator: Ator | None, acao: str, alvo: str | None = None, detalhe=None, empresa_id: str | None = None):
        self.banco.executar(
            "INSERT INTO auditoria(id, quando, usuario_id, empresa_id, acao, alvo, detalhe, ip) VALUES (?,?,?,?,?,?,?,?)",
            (novo_id(), self.agora(), ator.usuario_id if ator else None,
             empresa_id if empresa_id is not None else (ator.empresa_id if ator else None),
             acao, alvo, json.dumps(detalhe, ensure_ascii=False) if detalhe is not None else None, ator.ip if ator else None))

    def listar_auditoria(self, ator: Ator, empresa_id: str | None = None, limite: int = 200) -> list[dict]:
        ator.exigir("auditoria", "ver")
        if ator.plataforma and not empresa_id:
            return self.banco.todos("""SELECT a.*, u.nome AS usuario FROM auditoria a LEFT JOIN usuarios u ON u.id=a.usuario_id
                                        ORDER BY a.quando DESC LIMIT ?""", (limite,))
        eid = ator.empresa_alvo(empresa_id)
        return self.banco.todos("""SELECT a.*, u.nome AS usuario FROM auditoria a LEFT JOIN usuarios u ON u.id=a.usuario_id
                                    WHERE a.empresa_id=? ORDER BY a.quando DESC LIMIT ?""", (eid, limite))

    def avisar(self, texto_aviso: str, usuario_id: str | None = None, empresa_id: str | None = None,
               papel_alvo: str | None = None, link: str | None = None, conn=None):
        """Aviso dentro do sistema (sino). Para uma pessoa com celular cadastrado, vai também por WhatsApp quando ativado."""
        sql = "INSERT INTO notificacoes(id, usuario_id, empresa_id, papel_alvo, texto, link, criada_em) VALUES (?,?,?,?,?,?,?)"
        p = (novo_id(), usuario_id, empresa_id, papel_alvo, texto_aviso[:300], link, self.agora())
        (conn.execute if conn is not None else self.banco.executar)(sql, p)
        if usuario_id:
            self.enfileirar_whatsapp(usuario_id, "Sobrou+: " + texto_aviso, conn)
        if usuario_id or (empresa_id and papel_alvo in (None, "admin_empresa")):
            self.enfileirar_push(usuario_id, texto_aviso, link, empresa_id, papel_alvo, conn)

    def listar_avisos(self, ator: Ator, limite: int = 30) -> dict:
        cond, p = ["usuario_id=?"], [ator.usuario_id]
        if ator.empresa_id and ator.papel in PAPEIS_EMPRESA:
            cond.append("(usuario_id IS NULL AND empresa_id=? AND (papel_alvo IS NULL OR papel_alvo=?))")
            p += [ator.empresa_id, ator.papel]
        if ator.plataforma:
            cond.append("(usuario_id IS NULL AND empresa_id IS NULL AND papel_alvo='plataforma')")
        where = " OR ".join(cond)
        itens = self.banco.todos(f"SELECT * FROM notificacoes WHERE {where} ORDER BY criada_em DESC LIMIT ?", (*p, limite))
        nao = self.banco.um(f"SELECT COUNT(*) AS n FROM notificacoes WHERE lida=0 AND ({where})", tuple(p))["n"]
        return {"itens": itens, "nao_lidos": nao}

    def marcar_avisos_lidos(self, ator: Ator) -> dict:
        ids = [a["id"] for a in self.listar_avisos(ator, 200)["itens"]]
        for i in ids:
            self.banco.executar("UPDATE notificacoes SET lida=1 WHERE id=?", (i,))
        return {"ok": True}

    # ================================================================ LOGIN E SESSÃO
    def _usuario_publico(self, u: dict) -> dict:
        return {k: u.get(k) for k in ("id", "nome", "email", "telefone", "papel", "empresa_id", "instituicao_id",
                                      "ativo", "trocar_senha", "ultimo_acesso", "criado_em")} | {"papel_nome": PAPEIS.get(u["papel"])}

    def entrar(self, email: str, senha: str, ip: str | None = None, codigo: str | None = None) -> dict:
        e = (email or "").strip().lower()
        u = self.banco.um("SELECT * FROM usuarios WHERE email=?", (e,))
        agora = self.agora()
        if u and u["bloqueado_ate"] and u["bloqueado_ate"] > agora:
            raise ErroNegocio("Muitas tentativas. Aguarde alguns minutos e tente de novo.")
        if not u or not u["ativo"] or not seguranca.conferir_senha(senha or "", u["senha_salt"], u["senha_hash"]):
            if u:
                falhas = u["tentativas_falhas"] + 1
                espera = seguranca.duracao_bloqueio(falhas)
                ate = iso(self.agora_dt() + timedelta(seconds=espera)) if espera else None
                self.banco.executar("UPDATE usuarios SET tentativas_falhas=?, bloqueado_ate=? WHERE id=?", (falhas, ate, u["id"]))
            raise NaoAutenticado("E-mail ou senha incorretos.")
        if u["empresa_id"]:
            emp = self.banco.um("SELECT ativa FROM empresas WHERE id=?", (u["empresa_id"],))
            if emp and not emp["ativa"]:
                raise SemPermissao("O acesso desta empresa está bloqueado. Fale com a equipe Sobrou+.")
        if u.get("excluido_em"):
            raise NaoAutenticado("E-mail ou senha incorretos.")
        if u.get("totp_segredo"):
            from .acesso import PrecisaCodigo
            if not codigo:
                raise PrecisaCodigo("Digite o código de 6 números do aplicativo autenticador.")
            cont = seguranca.conferir_totp(u["totp_segredo"], codigo, u.get("totp_ultimo"))
            if cont is None:
                falhas = u["tentativas_falhas"] + 1
                espera = seguranca.duracao_bloqueio(falhas)
                self.banco.executar("UPDATE usuarios SET tentativas_falhas=?, bloqueado_ate=? WHERE id=?",
                                    (falhas, iso(self.agora_dt() + timedelta(seconds=espera)) if espera else None, u["id"]))
                raise PrecisaCodigo("Código incorreto ou vencido. Veja o código atual no aplicativo.")
            self.banco.executar("UPDATE usuarios SET totp_ultimo=? WHERE id=?", (cont, u["id"]))
        self.banco.executar("UPDATE usuarios SET tentativas_falhas=0, bloqueado_ate=NULL, ultimo_acesso=? WHERE id=?", (agora, u["id"]))
        return self._abrir_sessao(u, ip)

    def _abrir_sessao(self, u: dict, ip: str | None) -> dict:
        token = seguranca.novo_token()
        self.banco.executar("INSERT INTO sessoes(token_hash, usuario_id, criada_em, expira_em, ip) VALUES (?,?,?,?,?)",
                            (seguranca.hash_token(token), u["id"], self.agora(),
                             iso(self.agora_dt() + timedelta(hours=seguranca.DURACAO_SESSAO_HORAS)), ip))
        return {"token": token, "usuario": self._usuario_publico(u)}

    def entrar_com_token_unico(self, token_unico: str, ip: str | None = None) -> dict:
        r = seguranca.consumir_token_unico(token_unico)
        if not r:
            raise NaoAutenticado("Link de entrada inválido ou vencido.")
        u = self.banco.um("SELECT * FROM usuarios WHERE id=? AND ativo=1", (r[0],))
        if not u:
            raise NaoAutenticado("Usuário não encontrado.")
        return self._abrir_sessao(u, ip)

    def ator_da_sessao(self, token: str | None, ip: str | None = None) -> Ator:
        if not token:
            raise NaoAutenticado("Entre com seu e-mail e senha.")
        s = self.banco.um("""SELECT u.* FROM sessoes s JOIN usuarios u ON u.id=s.usuario_id
                              WHERE s.token_hash=? AND s.expira_em>? AND u.ativo=1""", (seguranca.hash_token(token), self.agora()))
        if not s:
            raise NaoAutenticado("Sua sessão terminou. Entre de novo.")
        if s["empresa_id"]:
            emp = self.banco.um("SELECT ativa FROM empresas WHERE id=?", (s["empresa_id"],))
            if emp and not emp["ativa"]:
                raise SemPermissao("O acesso desta empresa está bloqueado. Fale com a equipe Sobrou+.")
        return Ator(s["id"], s["papel"], s["nome"], s["empresa_id"], s["instituicao_id"], ip,
                    {"trocar_senha": bool(s["trocar_senha"]), "email": s["email"]})

    def sair(self, token: str) -> None:
        self.banco.executar("DELETE FROM sessoes WHERE token_hash=?", (seguranca.hash_token(token or ""),))

    def trocar_senha(self, ator: Ator, atual: str, nova: str) -> dict:
        u = self.banco.um("SELECT * FROM usuarios WHERE id=?", (ator.usuario_id,))
        if not u or not seguranca.conferir_senha(atual or "", u["senha_salt"], u["senha_hash"]):
            raise ErroNegocio("A senha atual não confere.")
        try:
            seguranca.validar_senha_nova(nova)
        except seguranca.SenhaFraca as e:
            raise ErroNegocio(str(e)) from e
        if nova == atual:
            raise ErroNegocio("A nova senha precisa ser diferente da atual.")
        salt = seguranca.gerar_salt()
        self.banco.executar("UPDATE usuarios SET senha_hash=?, senha_salt=?, trocar_senha=0 WHERE id=?",
                            (seguranca.hash_senha(nova, salt), salt, u["id"]))
        self.auditar(ator, "usuario.senha", u["id"])
        return {"ok": True}

    # ================================================================ USUÁRIOS
    def _inserir_usuario(self, nome, email, papel, senha=None, empresa_id=None, instituicao_id=None, telefone=None,
                         trocar=True) -> dict:
        if papel not in PAPEIS:
            raise ErroNegocio("Papel inválido.")
        e = _email(email)
        if self.banco.um("SELECT id FROM usuarios WHERE email=?", (e,)):
            raise ErroNegocio("Já existe uma conta com este e-mail.")
        if senha is None:
            senha, trocar = "1234", True  # senha inicial padrão; troca obrigatória no primeiro acesso
        salt = seguranca.gerar_salt()
        uid = novo_id()
        self.banco.executar(
            """INSERT INTO usuarios(id, empresa_id, instituicao_id, nome, email, telefone, senha_hash, senha_salt, papel,
                                    trocar_senha, criado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, empresa_id, instituicao_id, texto(nome, 120, True, "o nome"), e, texto(telefone, 30),
             seguranca.hash_senha(senha, salt), salt, papel, 1 if trocar else 0, self.agora()))
        return self.banco.um("SELECT * FROM usuarios WHERE id=?", (uid,))

    def cadastrar_cliente(self, dados: dict, ip: str | None = None) -> dict:
        if not dados.get("aceite_termos"):
            raise ErroNegocio("Para criar a conta, leia e aceite os Termos de Uso e a Política de Privacidade.")
        senha = dados.get("senha") or ""
        try:
            seguranca.validar_senha_nova(senha)
        except seguranca.SenhaFraca as e:
            raise ErroNegocio(str(e)) from e
        u = self._inserir_usuario(dados.get("nome"), dados.get("email"), "cliente", senha, telefone=dados.get("telefone"),
                                  trocar=False)
        self.registrar_aceite(u["id"])
        self.auditar(Ator(u["id"], "cliente", u["nome"], ip=ip), "cliente.cadastro", u["id"])
        return self._abrir_sessao(u, ip)

    def criar_usuario(self, ator: Ator, dados: dict) -> dict:
        ator.exigir("usuarios", "editar")
        papel = dados.get("papel")
        if ator.plataforma:
            empresa_id = dados.get("empresa_id") or None
            if papel in ("admin_empresa", "operador_empresa") and not empresa_id:
                raise ErroNegocio("Escolha a empresa deste usuário.")
        else:
            empresa_id = ator.empresa_id
            if papel not in PAPEIS_EMPRESA + ("entregador",):
                raise SemPermissao("Você só pode criar usuários da sua empresa.")
        if empresa_id:
            self.obter_empresa(ator, empresa_id)
        instituicao_id = dados.get("instituicao_id") if papel == "instituicao" else None
        if papel == "instituicao":
            if not ator.plataforma:
                raise SemPermissao("Contas de instituição são criadas pela equipe Sobrou+.")
            if not self.banco.um("SELECT id FROM instituicoes WHERE id=?", (instituicao_id,)):
                raise ErroNegocio("Escolha a instituição.")
            empresa_id = None
        u = self._inserir_usuario(dados.get("nome"), dados.get("email"), papel, None, empresa_id, instituicao_id,
                                  dados.get("telefone"))
        if papel == "entregador":
            self.banco.executar("INSERT INTO entregadores(id, usuario_id, empresa_id, tipo, veiculo, capacidade, criado_em) VALUES (?,?,?,?,?,?,?)",
                                (novo_id(), u["id"], empresa_id, "proprio" if empresa_id else dados.get("tipo_entregador", "sobrou"),
                                 texto(dados.get("veiculo"), 40), int(dados.get("capacidade") or 2), self.agora()))
        self.auditar(ator, "usuario.criar", u["id"], {"papel": papel}, empresa_id=empresa_id)
        token = self.gerar_convite(ator, u["id"])
        return {**self._usuario_publico(u), "convite": self._dados_convite(u, token)}

    def listar_usuarios(self, ator: Ator, empresa_id: str | None = None) -> list[dict]:
        ator.exigir("usuarios", "ver")
        if ator.plataforma and not empresa_id:
            linhas = self.banco.todos("SELECT * FROM usuarios WHERE papel<>'cliente' ORDER BY papel, nome")
        else:
            eid = ator.empresa_alvo(empresa_id)
            linhas = self.banco.todos("SELECT * FROM usuarios WHERE empresa_id=? ORDER BY papel, nome", (eid,))
        return [self._usuario_publico(u) for u in linhas]

    def ativar_usuario(self, ator: Ator, usuario_id: str, ativo: bool) -> dict:
        ator.exigir("usuarios", "editar")
        u = ator.conferir_empresa(self.banco.um("SELECT * FROM usuarios WHERE id=?", (usuario_id,)), "Usuário")
        if u["id"] == ator.usuario_id:
            raise ErroNegocio("Você não pode desativar a sua própria conta.")
        self.banco.executar("UPDATE usuarios SET ativo=? WHERE id=?", (1 if ativo else 0, usuario_id))
        if not ativo:
            self.banco.executar("DELETE FROM sessoes WHERE usuario_id=?", (usuario_id,))
        self.auditar(ator, "usuario.ativo" if ativo else "usuario.desativar", usuario_id, empresa_id=u["empresa_id"])
        return {"ok": True}

    def redefinir_senha(self, ator: Ator, usuario_id: str) -> dict:
        """Volta a senha para a inicial padrão, com troca obrigatória. A senha nunca é mostrada."""
        ator.exigir("usuarios", "editar")
        u = ator.conferir_empresa(self.banco.um("SELECT * FROM usuarios WHERE id=?", (usuario_id,)), "Usuário")
        salt = seguranca.gerar_salt()
        self.banco.executar("UPDATE usuarios SET senha_hash=?, senha_salt=?, trocar_senha=1, tentativas_falhas=0, bloqueado_ate=NULL WHERE id=?",
                            (seguranca.hash_senha("1234", salt), salt, usuario_id))
        self.banco.executar("DELETE FROM sessoes WHERE usuario_id=?", (usuario_id,))
        self.auditar(ator, "usuario.redefinir_senha", usuario_id, empresa_id=u["empresa_id"])
        return {"ok": True}

    def garantir_admin_sobrou(self, email: str, nome: str = "Administrador Sobrou+") -> dict:
        u = self.banco.um("SELECT * FROM usuarios WHERE email=?", (email.lower(),))
        return u or self._inserir_usuario(nome, email, "admin_sobrou")

    # ================================================================ EMPRESAS PARCEIRAS
    def _dados_empresa(self, dados: dict) -> dict:
        tipo = dados.get("tipo") or "restaurante"
        if tipo not in TIPOS_EMPRESA:
            raise ErroNegocio("Tipo de empresa inválido.")
        return {"nome": texto(dados.get("nome"), 120, True, "o nome da empresa"), "tipo": tipo,
                "documento": texto(dados.get("documento"), 30), "telefone": texto(dados.get("telefone"), 30),
                "email": texto(dados.get("email"), 160)}

    def _slug_livre(self, nome: str) -> str:
        base = slugificar(nome)
        slug, n = base, 2
        while self.banco.um("SELECT id FROM empresas WHERE slug=?", (slug,)):
            slug, n = f"{base}-{n}", n + 1
        return slug

    def cadastrar_empresa(self, dados: dict, ip: str | None = None) -> dict:
        """Cadastro público do parceiro: entra como 'aguardando aprovação' (não publica ofertas até a equipe aprovar)."""
        d = self._dados_empresa(dados)
        if not dados.get("aceite_termos"):
            raise ErroNegocio("Para cadastrar a empresa, leia e aceite os Termos de Uso e a Política de Privacidade.")
        senha = dados.get("senha") or ""
        try:
            seguranca.validar_senha_nova(senha)
        except seguranca.SenhaFraca as e:
            raise ErroNegocio(str(e)) from e
        _email(dados.get("email_responsavel"))
        if self.banco.um("SELECT id FROM usuarios WHERE email=?", ((dados.get("email_responsavel") or "").strip().lower(),)):
            raise ErroNegocio("Já existe uma conta com este e-mail.")
        eid = novo_id()
        self.banco.executar("""INSERT INTO empresas(id, nome, slug, tipo, documento, telefone, email, aprovada, criada_em)
                               VALUES (?,?,?,?,?,?,?,0,?)""",
                            (eid, d["nome"], self._slug_livre(d["nome"]), d["tipo"], d["documento"], d["telefone"], d["email"], self.agora()))
        self.banco.executar("INSERT INTO config_empresa(empresa_id) VALUES (?)", (eid,))
        u = self._inserir_usuario(dados.get("nome_responsavel") or d["nome"], dados.get("email_responsavel"), "admin_empresa",
                                  senha, eid, trocar=False)
        self.registrar_aceite(u["id"])
        self.auditar(Ator(u["id"], "admin_empresa", u["nome"], eid, ip=ip), "empresa.cadastro", eid)
        self.avisar(f"Nova empresa parceira aguardando aprovação: {d['nome']}", papel_alvo="plataforma")
        return self._abrir_sessao(u, ip)

    def criar_empresa(self, ator: Ator, dados: dict) -> dict:
        ator.exigir("empresas", "aprovar")
        d = self._dados_empresa(dados)
        eid = novo_id()
        self.banco.executar("""INSERT INTO empresas(id, nome, slug, tipo, documento, telefone, email, aprovada, taxa_percentual,
                               demonstracao, criada_em) VALUES (?,?,?,?,?,?,?,1,?,?,?)""",
                            (eid, d["nome"], self._slug_livre(d["nome"]), d["tipo"], d["documento"], d["telefone"], d["email"],
                             real(dados.get("taxa_percentual"), "a taxa", 0, 60), 1 if dados.get("demonstracao") else 0, self.agora()))
        self.banco.executar("INSERT INTO config_empresa(empresa_id) VALUES (?)", (eid,))
        if dados.get("plano_id"):
            self.banco.executar("UPDATE empresas SET plano_id=? WHERE id=?", (dados["plano_id"], eid))
        self.auditar(ator, "empresa.criar", eid, d, empresa_id=eid)
        r = self.obter_empresa(ator, eid)
        if (dados.get("email_responsavel") or "").strip():
            # o Desenvolvedor cadastra a empresa e já recebe o link de acesso para mandar ao responsável
            acesso = self.criar_usuario(ator, {"nome": dados.get("nome_responsavel") or d["nome"], "email": dados["email_responsavel"],
                                               "telefone": dados.get("telefone_responsavel") or d["telefone"], "papel": "admin_empresa", "empresa_id": eid})
            r["convite"] = acesso["convite"]
        return r

    def obter_empresa(self, ator: Ator, empresa_id: str) -> dict:
        e = self.banco.um("SELECT * FROM empresas WHERE id=?", (empresa_id,))
        if not e or not (ator.plataforma or ator.empresa_id == empresa_id):
            raise NaoEncontrado("Empresa não encontrada.")
        cfg = self.banco.um("SELECT * FROM config_empresa WHERE empresa_id=?", (empresa_id,)) or {}
        return {**e, "ativa": bool(e["ativa"]), "aprovada": bool(e["aprovada"]),
                "taxa_efetiva": self.taxa_da_empresa(e), "config": cfg}

    def taxa_da_empresa(self, empresa: dict) -> float:
        if empresa.get("taxa_percentual") is not None:
            return float(empresa["taxa_percentual"])
        if empresa.get("plano_id"):
            pl = self.banco.um("SELECT taxa_percentual FROM planos WHERE id=?", (empresa["plano_id"],))
            if pl:
                return float(pl["taxa_percentual"])
        v = self.banco.um("SELECT valor FROM config WHERE chave='taxa_padrao'")
        return float(v["valor"]) if v else TAXA_PADRAO

    def listar_empresas(self, ator: Ator) -> list[dict]:
        ator.exigir("empresas", "ver")
        if not ator.plataforma:
            return [self.obter_empresa(ator, ator.empresa_id)]
        return self.banco.todos("""SELECT e.*, (SELECT COUNT(*) FROM unidades u WHERE u.empresa_id=e.id) AS unidades,
                                          (SELECT COUNT(*) FROM ofertas o WHERE o.empresa_id=e.id AND o.status='ativa') AS ofertas_ativas
                                   FROM empresas e ORDER BY e.aprovada, e.nome""")

    def editar_empresa(self, ator: Ator, empresa_id: str, dados: dict) -> dict:
        ator.exigir("empresas", "editar")
        eid = ator.empresa_alvo(empresa_id)
        atual = self.obter_empresa(ator, eid)
        d = self._dados_empresa({**atual, **{k: v for k, v in dados.items() if v is not None}})
        self.banco.executar("UPDATE empresas SET nome=?, tipo=?, documento=?, telefone=?, email=? WHERE id=?",
                            (d["nome"], d["tipo"], d["documento"], d["telefone"], d["email"], eid))
        cfg = dados.get("config") or {}
        if cfg:
            atual_cfg = atual["config"]
            tema = cfg.get("tema", atual_cfg.get("tema"))
            if tema not in TEMAS + ("padrao",):
                raise ErroNegocio("Tema inválido.")
            from .nucleo import centavos
            self.banco.executar(
                """UPDATE config_empresa SET tema=?, nome_exibicao=?, aceita_retirada=?, aceita_entrega=?,
                   taxa_entrega_centavos=?, raio_entrega_km=?, pix_tipo=?, pix_chave=?, titular=?, banco=?, whatsapp_loja=? WHERE empresa_id=?""",
                (tema, texto(cfg.get("nome_exibicao", atual_cfg.get("nome_exibicao")), 80),
                 1 if cfg.get("aceita_retirada", atual_cfg.get("aceita_retirada", 1)) else 0,
                 1 if cfg.get("aceita_entrega", atual_cfg.get("aceita_entrega", 0)) else 0,
                 centavos(cfg.get("taxa_entrega_centavos", atual_cfg.get("taxa_entrega_centavos", 0)), "a taxa de entrega"),
                 real(cfg.get("raio_entrega_km", atual_cfg.get("raio_entrega_km", 5)), "o raio de entrega", 0.5, 50),
                 texto(cfg.get("pix_tipo", atual_cfg.get("pix_tipo")), 20), texto(cfg.get("pix_chave", atual_cfg.get("pix_chave")), 120),
                 texto(cfg.get("titular", atual_cfg.get("titular")), 120), texto(cfg.get("banco", atual_cfg.get("banco")), 80),
                 texto(cfg.get("whatsapp_loja", atual_cfg.get("whatsapp_loja")), 30), eid))
            if any(k in cfg for k in ("pix_chave", "pix_tipo", "titular", "banco")):
                self.auditar(ator, "empresa.dados_repasse", eid, empresa_id=eid)
        if ator.plataforma and "taxa_percentual" in dados:
            self.banco.executar("UPDATE empresas SET taxa_percentual=? WHERE id=?",
                                (real(dados.get("taxa_percentual"), "a taxa", 0, 60), eid))
        self.auditar(ator, "empresa.editar", eid, {"campos": sorted(dados.keys())}, empresa_id=eid)
        return self.obter_empresa(ator, eid)

    def aprovar_empresa(self, ator: Ator, empresa_id: str, aprovada: bool = True, ativa: bool | None = None) -> dict:
        ator.exigir("empresas", "aprovar")
        self.obter_empresa(ator, empresa_id)
        self.banco.executar("UPDATE empresas SET aprovada=? WHERE id=?", (1 if aprovada else 0, empresa_id))
        if ativa is not None:
            self.banco.executar("UPDATE empresas SET ativa=? WHERE id=?", (1 if ativa else 0, empresa_id))
            if not ativa:
                self.banco.executar("DELETE FROM sessoes WHERE usuario_id IN (SELECT id FROM usuarios WHERE empresa_id=?)", (empresa_id,))
        self.auditar(ator, "empresa.aprovar", empresa_id, {"aprovada": aprovada, "ativa": ativa}, empresa_id=empresa_id)
        self.avisar("Sua empresa foi aprovada no Sobrou+. Já pode publicar ofertas." if aprovada else
                    "O cadastro da sua empresa está em análise pela equipe Sobrou+.", empresa_id=empresa_id, papel_alvo="admin_empresa")
        return self.obter_empresa(ator, empresa_id)

    # ================================================================ UNIDADES
    def salvar_unidade(self, ator: Ator, dados: dict, unidade_id: str | None = None) -> dict:
        ator.exigir("unidades", "editar")
        if unidade_id:
            atual = ator.conferir_empresa(self.banco.um("SELECT * FROM unidades WHERE id=?", (unidade_id,)), "Unidade")
            eid = atual["empresa_id"]
            dados = {**atual, **dados}
        else:
            eid = ator.empresa_alvo(dados.get("empresa_id"))
        lat = real(dados.get("lat"), "a latitude", -90, 90)
        lng = real(dados.get("lng"), "a longitude", -180, 180)
        valores = (texto(dados.get("nome"), 120, True, "o nome da unidade"), texto(dados.get("endereco"), 200),
                   texto(dados.get("bairro"), 80), texto(dados.get("cidade"), 80), lat, lng, texto(dados.get("telefone"), 30),
                   texto(dados.get("instrucoes_retirada"), 300), 0 if dados.get("ativa") in (0, False, "0") else 1)
        if unidade_id:
            self.banco.executar("""UPDATE unidades SET nome=?, endereco=?, bairro=?, cidade=?, lat=?, lng=?, telefone=?,
                                   instrucoes_retirada=?, ativa=? WHERE id=?""", (*valores, unidade_id))
        else:
            unidade_id = novo_id()
            self.banco.executar("""INSERT INTO unidades(nome, endereco, bairro, cidade, lat, lng, telefone, instrucoes_retirada, ativa,
                                   id, empresa_id, criada_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (*valores, unidade_id, eid, self.agora()))
        self.auditar(ator, "unidade.salvar", unidade_id, {"nome": valores[0]}, empresa_id=eid)
        return self.banco.um("SELECT * FROM unidades WHERE id=?", (unidade_id,))

    def listar_unidades(self, ator: Ator, empresa_id: str | None = None) -> list[dict]:
        ator.exigir("unidades", "ver")
        if ator.plataforma and not empresa_id:
            return self.banco.todos("SELECT u.*, e.nome AS empresa FROM unidades u JOIN empresas e ON e.id=u.empresa_id ORDER BY e.nome, u.nome")
        eid = ator.empresa_alvo(empresa_id)
        return self.banco.todos("SELECT * FROM unidades WHERE empresa_id=? ORDER BY nome", (eid,))

    # ================================================================ INSTITUIÇÕES
    def salvar_instituicao(self, ator: Ator | None, dados: dict, instituicao_id: str | None = None) -> dict:
        """Equipe Sobrou+ cadastra/edita. Cadastro público (ator=None) entra como NÃO autorizada."""
        if ator is not None:
            ator.exigir("instituicoes", "autorizar")
        elif not dados.get("aceite_termos"):
            raise ErroNegocio("Para enviar o cadastro, leia e aceite os Termos de Uso e a Política de Privacidade.")
        valores = (texto(dados.get("nome"), 140, True, "o nome da instituição"), texto(dados.get("documento"), 30),
                   texto(dados.get("responsavel"), 120, True, "o responsável"), texto(dados.get("telefone"), 30),
                   texto(dados.get("endereco"), 200), texto(dados.get("cidade"), 80),
                   int(dados.get("pessoas_atendidas") or 0))
        if instituicao_id:
            if not self.banco.um("SELECT id FROM instituicoes WHERE id=?", (instituicao_id,)):
                raise NaoEncontrado("Instituição não encontrada.")
            self.banco.executar("""UPDATE instituicoes SET nome=?, documento=?, responsavel=?, telefone=?, endereco=?, cidade=?,
                                   pessoas_atendidas=? WHERE id=?""", (*valores, instituicao_id))
        else:
            instituicao_id = novo_id()
            self.banco.executar("""INSERT INTO instituicoes(nome, documento, responsavel, telefone, endereco, cidade, pessoas_atendidas,
                                   id, criada_em) VALUES (?,?,?,?,?,?,?,?,?)""", (*valores, instituicao_id, self.agora()))
            if ator is None:
                self.avisar(f"Nova instituição pediu cadastro: {valores[0]}", papel_alvo="plataforma")
        self.auditar(ator, "instituicao.salvar", instituicao_id, {"nome": valores[0]}, empresa_id=None)
        return self.banco.um("SELECT * FROM instituicoes WHERE id=?", (instituicao_id,))

    def autorizar_instituicao(self, ator: Ator, instituicao_id: str, autorizada: bool) -> dict:
        ator.exigir("instituicoes", "autorizar")
        if not self.banco.um("SELECT id FROM instituicoes WHERE id=?", (instituicao_id,)):
            raise NaoEncontrado("Instituição não encontrada.")
        self.banco.executar("UPDATE instituicoes SET autorizada=?, autorizada_por=?, autorizada_em=? WHERE id=?",
                            (1 if autorizada else 0, ator.usuario_id, self.agora(), instituicao_id))
        self.auditar(ator, "instituicao.autorizar", instituicao_id, {"autorizada": autorizada}, empresa_id=None)
        return self.banco.um("SELECT * FROM instituicoes WHERE id=?", (instituicao_id,))

    def listar_instituicoes(self, ator: Ator, so_autorizadas: bool = False) -> list[dict]:
        if ator.papel == "instituicao":
            return self.banco.todos("SELECT * FROM instituicoes WHERE id=?", (ator.instituicao_id,))
        ator.exigir("instituicoes", "ver")
        if so_autorizadas or not ator.plataforma:
            return self.banco.todos("SELECT id, nome, responsavel, cidade, pessoas_atendidas, autorizada FROM instituicoes WHERE autorizada=1 ORDER BY nome")
        return self.banco.todos("SELECT * FROM instituicoes ORDER BY autorizada, nome")

    # ================================================================ CONFIGURAÇÃO DA PLATAFORMA
    def config_plataforma(self) -> dict:
        linhas = {l["chave"]: l["valor"] for l in self.banco.todos("SELECT * FROM config")}
        return {"tema": linhas.get("tema", "claro"), "taxa_padrao": float(linhas.get("taxa_padrao", TAXA_PADRAO)),
                "nome_exibicao": linhas.get("nome_exibicao", "Sobrou+"),
                "minutos_reserva": int(linhas.get("minutos_reserva", 15)),
                "tolerancia_retirada_min": int(linhas.get("tolerancia_retirada_min", 30)),
                "email_contato": linhas.get("email_contato") or "", "whatsapp_suporte": linhas.get("whatsapp_suporte") or ""}

    def salvar_config_plataforma(self, ator: Ator, dados: dict) -> dict:
        ator.exigir("sistema", "ver")
        regras = {"tema": lambda v: v if v in TEMAS else (_ for _ in ()).throw(ErroNegocio("Tema inválido.")),
                  "taxa_padrao": lambda v: str(real(v, "a taxa padrão", 0, 60, True)),
                  "nome_exibicao": lambda v: texto(v, 60, True, "o nome"),
                  "minutos_reserva": lambda v: str(max(5, min(60, int(v)))),
                  "tolerancia_retirada_min": lambda v: str(max(0, min(240, int(v)))),
                  "email_contato": lambda v: texto(v, 160) or "",
                  "whatsapp_suporte": lambda v: texto(v, 30) or ""}
        for chave, conv in regras.items():
            if chave in dados:
                self.banco.executar("INSERT INTO config(chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                                    (chave, conv(dados[chave])))
        self.auditar(ator, "config.plataforma", None, dados, empresa_id=None)
        return self.config_plataforma()
