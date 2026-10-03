"""Acesso: entrada do Desenvolvedor só com senha (+ verificação em 2 etapas opcional), link de acesso (convite) para
empresas/entregadores/equipe, e Modo teste do Desenvolvedor (abrir todas as telas com contas de TESTE)."""
from __future__ import annotations

import secrets
from datetime import timedelta

from . import seguranca
from .nucleo import PAPEIS, Ator, ErroNegocio, NaoAutenticado, NaoEncontrado, SemPermissao, iso, novo_id, texto

DIAS_CONVITE = 7
PERFIS_TESTE = {
    "cliente": ("Cliente (teste RMD)", "cliente"),
    "entregador": ("Entregador (teste RMD)", "entregador"),
    "operador_empresa": ("Balcão (teste RMD)", "operador_empresa"),
    "admin_empresa": ("Empresa (teste RMD)", "admin_empresa"),
    "financeiro": ("Financeiro da empresa (teste RMD)", "financeiro"),
    "logistica": ("Logística da empresa (teste RMD)", "logistica"),
    "instituicao": ("Instituição (teste RMD)", "instituicao"),
}


class PrecisaCodigo(NaoAutenticado):
    """Senha certa, falta o código de 6 números do aplicativo autenticador."""


class AcessoMixin:
    # ================================================================ DESENVOLVEDOR RMD
    def definir_dono(self, email: str) -> dict:
        """O Desenvolvedor entra só com a senha. Senha inicial padrão, SEM troca obrigatória (pode trocar em Configurações)."""
        u = self.garantir_admin_sobrou(email, "Desenvolvedor RMD")
        self.banco.executar("UPDATE usuarios SET trocar_senha=0, papel='admin_sobrou', ativo=1 WHERE id=?", (u["id"],))
        self.banco.executar("INSERT INTO config(chave, valor) VALUES ('dono_id', ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (u["id"],))
        return u

    def id_dono(self) -> str | None:
        r = self.banco.um("SELECT valor FROM config WHERE chave='dono_id'")
        return r["valor"] if r else None

    def entrar_criador(self, senha: str, ip: str | None = None, codigo: str | None = None) -> dict:
        dono = self.banco.um("SELECT email FROM usuarios WHERE id=?", (self.id_dono() or "",))
        if not dono:
            raise NaoAutenticado("Acesso do Desenvolvedor RMD ainda não configurado neste servidor.")
        return self.entrar(dono["email"], senha, ip, codigo)

    def senha_padrao(self, ator: Ator) -> bool:
        u = self.banco.um("SELECT senha_hash, senha_salt FROM usuarios WHERE id=?", (ator.usuario_id,))
        return bool(u) and seguranca.conferir_senha("1234", u["senha_salt"], u["senha_hash"])

    # ---------------------------------------------------------------- verificação em 2 etapas (aplicativo autenticador)
    def iniciar_2fa(self, ator: Ator) -> dict:
        segredo = seguranca.gerar_segredo_totp()
        self.banco.executar("INSERT INTO config(chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                            ("2fa_pendente:" + ator.usuario_id, segredo))
        email = ator.extras.get("email") or "desenvolvedor-rmd"
        return {"segredo": segredo, "endereco": seguranca.endereco_totp(segredo, email, "Sobrou+")}

    def confirmar_2fa(self, ator: Ator, codigo: str) -> dict:
        r = self.banco.um("SELECT valor FROM config WHERE chave=?", ("2fa_pendente:" + ator.usuario_id,))
        if not r:
            raise ErroNegocio("Comece a ativação de novo.")
        cont = seguranca.conferir_totp(r["valor"], codigo)
        if cont is None:
            raise ErroNegocio("Código não confere. Veja o código de 6 números no aplicativo e tente de novo.")
        self.banco.executar("UPDATE usuarios SET totp_segredo=?, totp_ultimo=? WHERE id=?", (r["valor"], cont, ator.usuario_id))
        self.banco.executar("DELETE FROM config WHERE chave=?", ("2fa_pendente:" + ator.usuario_id,))
        self.auditar(ator, "seguranca.2fa_ligar", ator.usuario_id, empresa_id=ator.empresa_id)
        return {"ok": True}

    def desligar_2fa(self, ator: Ator, senha: str) -> dict:
        u = self.banco.um("SELECT * FROM usuarios WHERE id=?", (ator.usuario_id,))
        if not seguranca.conferir_senha(senha or "", u["senha_salt"], u["senha_hash"]):
            raise ErroNegocio("Senha incorreta.")
        self.banco.executar("UPDATE usuarios SET totp_segredo=NULL, totp_ultimo=NULL WHERE id=?", (ator.usuario_id,))
        self.auditar(ator, "seguranca.2fa_desligar", ator.usuario_id, empresa_id=ator.empresa_id)
        return {"ok": True}

    def sair_de_todos(self, ator: Ator, token_atual: str) -> dict:
        n = self.banco.executar("DELETE FROM sessoes WHERE usuario_id=? AND token_hash<>?", (ator.usuario_id, seguranca.hash_token(token_atual or "")))
        self.auditar(ator, "seguranca.sair_todos", ator.usuario_id, {"sessoes": n}, empresa_id=ator.empresa_id)
        return {"ok": True, "encerradas": n}

    def sessoes_ativas(self, ator: Ator) -> list[dict]:
        return self.banco.todos("SELECT criada_em, expira_em, ip FROM sessoes WHERE usuario_id=? AND expira_em>? ORDER BY criada_em DESC",
                                (ator.usuario_id, self.agora()))

    # ================================================================ LINK DE ACESSO (CONVITE)
    def gerar_convite(self, ator: Ator | None, usuario_id: str) -> str:
        token = secrets.token_urlsafe(24)
        self.banco.executar("UPDATE convites SET usado_em=? WHERE usuario_id=? AND usado_em IS NULL", (self.agora(), usuario_id))
        self.banco.executar("INSERT INTO convites(id, usuario_id, token_hash, expira_em, criado_por, criado_em) VALUES (?,?,?,?,?,?)",
                            (novo_id(), usuario_id, seguranca.hash_token(token), iso(self.agora_dt() + timedelta(days=DIAS_CONVITE)),
                             ator.usuario_id if ator else None, self.agora()))
        return token

    def novo_convite(self, ator: Ator, usuario_id: str) -> dict:
        ator.exigir("usuarios", "editar")
        u = ator.conferir_empresa(self.banco.um("SELECT * FROM usuarios WHERE id=?", (usuario_id,)), "Usuário")
        if u["id"] == self.id_dono():
            raise SemPermissao("O acesso do Desenvolvedor RMD não usa link.")
        token = self.gerar_convite(ator, usuario_id)
        self.auditar(ator, "usuario.convite", usuario_id, empresa_id=u["empresa_id"])
        return self._dados_convite(u, token)

    def _dados_convite(self, u: dict, token: str) -> dict:
        emp = self.banco.um("SELECT nome FROM empresas WHERE id=?", (u["empresa_id"],)) if u.get("empresa_id") else None
        return {"usuario_id": u["id"], "nome": u["nome"], "email": u["email"], "telefone": u.get("telefone"), "papel": u["papel"],
                "papel_nome": PAPEIS.get(u["papel"]), "empresa": emp["nome"] if emp else None,
                "caminho": f"/acesso?c={token}", "validade_dias": DIAS_CONVITE}

    def _convite_valido(self, token: str) -> tuple[dict, dict]:
        c = self.banco.um("SELECT * FROM convites WHERE token_hash=?", (seguranca.hash_token(token or ""),))
        if not c or c["usado_em"] or c["expira_em"] <= self.agora():
            raise NaoEncontrado("Este link de acesso não vale mais. Peça um novo para quem cadastrou você.")
        u = self.banco.um("SELECT * FROM usuarios WHERE id=? AND ativo=1", (c["usuario_id"],))
        if not u:
            raise NaoEncontrado("Este acesso foi desativado.")
        return c, u

    def ver_convite(self, token: str) -> dict:
        _c, u = self._convite_valido(token)
        emp = self.banco.um("SELECT nome FROM empresas WHERE id=?", (u["empresa_id"],)) if u["empresa_id"] else None
        return {"nome": u["nome"], "email": u["email"], "papel_nome": PAPEIS.get(u["papel"]), "empresa": emp["nome"] if emp else None}

    def aceitar_convite(self, token: str, senha: str, aceite_termos: bool, ip: str | None = None) -> dict:
        c, u = self._convite_valido(token)
        if not aceite_termos:
            raise ErroNegocio("Para continuar, leia e aceite os Termos de Uso e a Política de Privacidade.")
        try:
            seguranca.validar_senha_nova(senha)
        except seguranca.SenhaFraca as e:
            raise ErroNegocio(str(e)) from e
        salt = seguranca.gerar_salt()
        self.banco.executar("UPDATE usuarios SET senha_hash=?, senha_salt=?, trocar_senha=0, tentativas_falhas=0, bloqueado_ate=NULL WHERE id=?",
                            (seguranca.hash_senha(senha, salt), salt, u["id"]))
        self.banco.executar("UPDATE convites SET usado_em=? WHERE id=?", (self.agora(), c["id"]))
        self.registrar_aceite(u["id"])
        self.auditar(Ator(u["id"], u["papel"], u["nome"], u["empresa_id"], ip=ip), "usuario.convite_aceito", u["id"], empresa_id=u["empresa_id"])
        return self._abrir_sessao(self.banco.um("SELECT * FROM usuarios WHERE id=?", (u["id"],)), ip)

    # ================================================================ MODO TESTE RMD
    def mundo_de_teste(self) -> dict:
        """Uma loja de TESTE (marcada como demonstração) com contas de teste para cada perfil. Nunca mistura com clientes reais."""
        r = self.banco.um("SELECT valor FROM config WHERE chave='teste_empresa_id'")
        eid = r["valor"] if r else None
        if not eid or not self.banco.um("SELECT id FROM empresas WHERE id=?", (eid,)):
            eid = novo_id()
            self.banco.executar("""INSERT INTO empresas(id, nome, slug, tipo, aprovada, demonstracao, criada_em)
                                   VALUES (?,?,?,?,1,1,?)""", (eid, "Loja Teste RMD", self._slug_livre("loja-teste-rmd"), "restaurante", self.agora()))
            self.banco.executar("INSERT INTO config_empresa(empresa_id, aceita_entrega, taxa_entrega_centavos, raio_entrega_km) VALUES (?,1,600,10)", (eid,))
            self.banco.executar("""INSERT INTO unidades(id, empresa_id, nome, endereco, cidade, lat, lng, instrucoes_retirada, criada_em)
                                   VALUES (?,?,?,?,?,?,?,?,?)""", (novo_id(), eid, "Unidade de teste", "Endereço de teste", "Aracaju", -10.9111, -37.0717,
                                                                     "Balcão (teste)", self.agora()))
            self.banco.executar("INSERT INTO config(chave, valor) VALUES ('teste_empresa_id', ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (eid,))
        inst = self.banco.um("SELECT valor FROM config WHERE chave='teste_instituicao_id'")
        iid = inst["valor"] if inst else None
        if not iid or not self.banco.um("SELECT id FROM instituicoes WHERE id=?", (iid,)):
            iid = novo_id()
            self.banco.executar("""INSERT INTO instituicoes(id, nome, responsavel, cidade, autorizada, autorizada_em, criada_em)
                                   VALUES (?,?,?,?,1,?,?)""", (iid, "Instituição Teste RMD", "Teste", "Aracaju", self.agora(), self.agora()))
            self.banco.executar("INSERT INTO config(chave, valor) VALUES ('teste_instituicao_id', ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (iid,))
        ids = {}
        for perfil, (nome, papel) in PERFIS_TESTE.items():
            email = f"teste-{perfil.replace('_', '-')}@rmd.sobrou.invalid"
            u = self.banco.um("SELECT id FROM usuarios WHERE email=?", (email,))
            if not u:
                u = self._inserir_usuario(nome, email, papel, secrets.token_urlsafe(18) + "a1",
                                          eid if papel in ("admin_empresa", "operador_empresa", "financeiro", "logistica") else None,
                                          iid if papel == "instituicao" else None, trocar=False)
                if papel == "entregador":
                    self.banco.executar("INSERT INTO entregadores(id, usuario_id, empresa_id, tipo, veiculo, capacidade, criado_em) VALUES (?,?,?,?,?,?,?)",
                                        (novo_id(), u["id"], eid, "proprio", "Moto (teste)", 3, self.agora()))
            ids[perfil] = u["id"]
        if not self.banco.um("SELECT id FROM ofertas WHERE empresa_id=? LIMIT 1", (eid,)):
            uni = self.banco.um("SELECT id FROM unidades WHERE empresa_id=?", (eid,))["id"]
            agora = self.agora()
            for nome, tipo, cat, normal, preco, qtd, vmin, vmax in (("Marmita Executiva", "produto", "refeicoes", 2490, 1250, 20, None, None),
                                                                     ("Cesta surpresa da padaria", "cesta", "cesta_surpresa", 3500, 1490, 20, 3500, 5000)):
                oid = novo_id()
                self.banco.executar("""INSERT INTO ofertas(id, empresa_id, unidade_id, tipo, nome, descricao, categoria, preco_normal_centavos, preco_centavos,
                                       preco_base_centavos, valor_estimado_min_centavos, valor_estimado_max_centavos, quantidade_total, inicio, fim,
                                       retirada_inicio, retirada_fim, permite_retirada, permite_entrega, status, criada_em, atualizada_em)
                                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,1,'ativa',?,?)""",
                                    (oid, eid, uni, tipo, nome, "Oferta de TESTE RMD (imagem ilustrativa)", cat, normal, preco, preco, vmin, vmax, qtd,
                                     agora, agora, agora, agora, agora, agora))
        from . import demo
        demo._garantir_fotos(self)
        demo._renovar_ofertas(self)
        return {"empresa_id": eid, "instituicao_id": iid, "usuarios": ids}

    def abrir_teste(self, ator: Ator, perfil: str) -> str:
        """Só o Desenvolvedor. Devolve um link de entrada de uso único (90 s) numa conta de TESTE."""
        if ator.usuario_id != self.id_dono() and ator.papel != "admin_sobrou":
            raise SemPermissao("Só o Desenvolvedor RMD usa o modo teste.")
        if perfil not in PERFIS_TESTE:
            raise NaoEncontrado("Perfil de teste desconhecido.")
        uid = self.mundo_de_teste()["usuarios"][perfil]
        self.auditar(ator, "criador.modo_teste", perfil, empresa_id=None)
        return seguranca.criar_token_unico(uid, None)

    def eh_conta_teste(self, usuario_id: str) -> bool:
        u = self.banco.um("SELECT email FROM usuarios WHERE id=?", (usuario_id,))
        return bool(u) and u["email"].endswith(("@rmd.sobrou.invalid", "@criador.sobrou.invalid"))
